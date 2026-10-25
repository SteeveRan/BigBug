/**
 * @file Settings/SyncRuns/index.tsx
 * @description Admin Sync Runs page (issue #113): operational view of tracked
 *              background task runs — status filters (incl. Failed permanent
 *              DLQ and Stuck), traceback in expandable row, recovery actions
 *              (retry / requeue / retry-all-failed). Backend: /api/admin/sync-runs.
 * @dependencies antd, ../../store/api, ../../types
 * @relatedFiles ../../store/api/sync-runs.ts, ../AuditLog/index.tsx
 */

import { useMemo, useState } from 'react';
import { App, Button, Card, Flex, Popconfirm, Spin, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PermissionGate } from '../../../components/PermissionGate';
import { StatusChip } from '../../../components/StatusChip';
import type { SyncRun } from '../../../types';
import {
  useGetSyncRunsQuery,
  useRequeueSyncRunMutation,
  useRetryAllFailedMutation,
  useRetrySyncRunMutation,
} from '../../../store/api';

// Row status → StatusChip numeric convention:
// succeeded→0 (OK), failed/failed_permanent→1 (Failed),
// running→3 (In Progress), queued/superseded→4 (Pending). Stuck is a separate tag.
const STATUS_NUM: Record<string, number> = {
  succeeded: 0,
  failed: 1,
  failed_permanent: 1,
  running: 3,
  queued: 4,
  superseded: 4,
};

const STATUS_LABELS: Record<number, string> = {
  0: 'Succeeded',
  1: 'Failed',
  3: 'Running',
  4: 'Pending',
};

type StatusFilter =
  | 'all'
  | 'failed_permanent'
  | 'failed'
  | 'stuck'
  | 'running'
  | 'queued'
  | 'succeeded';

const FILTER_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'failed_permanent', label: 'Failed permanent' },
  { value: 'failed', label: 'Failed' },
  { value: 'stuck', label: 'Stuck' },
  { value: 'running', label: 'Running' },
  { value: 'queued', label: 'Queued' },
  { value: 'succeeded', label: 'Succeeded' },
];

function formatTimestamp(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : '-';
}

export default function SyncRunsPage() {
  const { message } = App.useApp();
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [page, setPage] = useState(1);

  const params = useMemo(() => {
    if (filter === 'all') return {};
    if (filter === 'stuck') return { stuck: true };
    return { run_status: filter };
  }, [filter]);

  const { data, isLoading, isFetching, isError } = useGetSyncRunsQuery(params, {
    pollingInterval: 30_000,
  });
  const [retrySyncRun, { isLoading: retrying }] = useRetrySyncRunMutation();
  const [retryAllFailed, { isLoading: retryingAll }] = useRetryAllFailedMutation();
  const [requeueSyncRun, { isLoading: requeuing }] = useRequeueSyncRunMutation();

  const runs = useMemo(() => data ?? [], [data]);

  // Client-side slice: the backend list endpoint has no pagination.
  const pageData = runs.slice((page - 1) * 50, page * 50);

  const failedPermanentCount = runs.filter((r) => r.status === 'failed_permanent').length;

  const handleAction = async (action: () => Promise<unknown>, success: string) => {
    try {
      const res = (await action()) as { retried?: number } | undefined;
      message.success(res?.retried !== undefined ? `${success}: ${res.retried}` : success);
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Action failed');
    }
  };

  const columns: ColumnsType<SyncRun> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    { title: 'Task', dataIndex: 'task_name', key: 'task_name' },
    {
      title: 'Entity',
      key: 'entity',
      render: (_: unknown, r: SyncRun) =>
        r.entity_type ? `${r.entity_type}#${r.entity_id ?? '-'}` : '-',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (_: unknown, r: SyncRun) => (
        <Flex gap={4} align="center">
          <StatusChip
            status={STATUS_NUM[r.status] ?? 4}
            labels={STATUS_LABELS}
            statusText={r.status === 'failed_permanent' ? 'Failed permanent' : undefined}
          />
          {r.stuck && <Tag color="warning">Stuck</Tag>}
        </Flex>
      ),
    },
    {
      title: 'Attempts',
      key: 'attempts',
      render: (_: unknown, r: SyncRun) => `${r.attempts}/${r.max_attempts}`,
      width: 90,
    },
    {
      title: 'Heartbeat',
      dataIndex: 'heartbeat_at',
      key: 'heartbeat_at',
      render: (v: string | null) => formatTimestamp(v),
    },
    {
      title: 'Started',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string | null) => formatTimestamp(v),
    },
    {
      title: 'Finished',
      dataIndex: 'finished_at',
      key: 'finished_at',
      render: (v: string | null) => formatTimestamp(v),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, r: SyncRun) => {
        const retryable = r.status === 'failed' || r.status === 'failed_permanent';
        if (!retryable && !r.stuck) return null;
        return (
          <PermissionGate permission="system:config">
            <Flex gap={8}>
              {retryable && (
                <Button
                  size="small"
                  type="link"
                  loading={retrying}
                  onClick={() =>
                    handleAction(() => retrySyncRun(r.id).unwrap(), `Run #${r.id} re-enqueued`)
                  }
                >
                  Retry
                </Button>
              )}
              {r.stuck && (
                <Button
                  size="small"
                  type="link"
                  loading={requeuing}
                  onClick={() =>
                    handleAction(() => requeueSyncRun(r.id).unwrap(), `Run #${r.id} requeued`)
                  }
                >
                  Requeue
                </Button>
              )}
            </Flex>
          </PermissionGate>
        );
      },
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={12}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Sync Runs
        </Typography.Title>
        <PermissionGate permission="system:config">
          <PopconfirmRetryAll
            count={failedPermanentCount}
            loading={retryingAll}
            onConfirm={() =>
              handleAction(() => retryAllFailed().unwrap(), 'Failed permanent runs re-enqueued')
            }
          />
        </PermissionGate>
      </Flex>

      {/* Status filters */}
      <Flex gap={4} wrap="wrap">
        {FILTER_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            size="small"
            type={filter === opt.value ? 'primary' : 'default'}
            onClick={() => {
              setFilter(opt.value);
              setPage(1);
            }}
          >
            {opt.label}
            {opt.value === 'failed_permanent' && failedPermanentCount > 0
              ? ` (${failedPermanentCount})`
              : ''}
          </Button>
        ))}
      </Flex>

      {/* Loading */}
      {isLoading && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin />
        </Flex>
      )}

      {/* Error state */}
      {isError && !isLoading && (
        <Typography.Text type="danger">Failed to load sync runs</Typography.Text>
      )}

      {/* Empty state */}
      {!isLoading && !isError && runs.length === 0 && (
        <Typography.Text
          type="secondary"
          style={{ padding: '40px 0', textAlign: 'center', display: 'block' }}
        >
          No sync runs found
        </Typography.Text>
      )}

      {/* Table */}
      {!isLoading && !isError && runs.length > 0 && (
        <Card>
          <Table
            columns={columns}
            dataSource={pageData}
            rowKey="id"
            size="small"
            loading={isFetching}
            expandable={{
              expandedRowRender: (r) =>
                r.error ? (
                  <pre
                    style={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontFamily: 'monospace',
                      fontSize: 12,
                    }}
                  >
                    {r.error}
                  </pre>
                ) : (
                  <Typography.Text type="secondary">No error</Typography.Text>
                ),
              rowExpandable: (r) => Boolean(r.error),
            }}
            pagination={{
              current: page,
              pageSize: 50,
              total: runs.length,
              onChange: setPage,
              showSizeChanger: false,
            }}
          />
        </Card>
      )}
    </Flex>
  );
}

function PopconfirmRetryAll({
  count,
  loading,
  onConfirm,
}: {
  count: number;
  loading: boolean;
  onConfirm: () => void;
}) {
  return (
    <Popconfirm
      title={`Retry all ${count} failed permanent run(s)?`}
      onConfirm={onConfirm}
      disabled={count === 0}
    >
      <Button danger type="primary" disabled={count === 0} loading={loading}>
        Retry All Failed{count > 0 ? ` (${count})` : ''}
      </Button>
    </Popconfirm>
  );
}
