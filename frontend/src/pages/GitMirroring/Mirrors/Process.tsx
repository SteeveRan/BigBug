/**
 * @file Mirrors/Process.tsx
 * @description Страница Mirror Process с тремя табами: Process, Configuration, Logs
 * @dependencies antd, react-router, RTK Query, PermissionGate, StatusChip
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Tabs,
  Descriptions,
  Table,
  Tag,
  Button,
  Flex,
  Space,
  Spin,
  Alert,
  Empty,
  Breadcrumb,
  Tooltip,
  Select,
  App,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  SyncOutlined,
  CheckCircleOutlined,
  SafetyCertificateOutlined,
  EditOutlined,
  LinkOutlined,
  GithubOutlined,
  GitlabOutlined,
} from '@ant-design/icons';
import {
  useGetMirrorDetailQuery,
  useGetMirrorLogsV2Query,
  useTriggerMirrorSyncMutation,
  useTriggerFreshnessCheckMutation,
} from '../../../store/api';
import type { MirrorLog } from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';

const LOG_TYPE_OPTIONS = [
  { label: 'All', value: '' },
  { label: 'Sync', value: 'sync' },
  { label: 'Freshness', value: 'freshness' },
  { label: 'Integrity', value: 'integrity' },
  { label: 'Import', value: 'import' },
];

const STATUS_OPTIONS = [
  { label: 'All', value: -1 },
  { label: 'OK', value: 0 },
  { label: 'Failed', value: 1 },
  { label: 'Warning', value: 2 },
  { label: 'In Progress', value: 3 },
  { label: 'Pending', value: 4 },
];

const LOG_TAG_COLORS: Record<string, string> = {
  sync: 'blue',
  freshness: 'green',
  integrity: 'orange',
  import: 'purple',
  release: 'cyan',
};

const PAGE_SIZE_OPTIONS = ['10', '20', '50'];

/**
 * Форматирует дату для отображения в таблице.
 */
function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString();
}

/**
 * Форматирует длительность в читаемый вид.
 */
function formatDuration(ms?: number): string {
  if (ms === undefined || ms === null) return '—';
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSecs = seconds % 60;
  return `${minutes}m ${remainingSecs}s`;
}

/**
 * Сокращает SHA до первых 7 символов.
 */
function shortSha(sha?: string): string {
  if (!sha) return '—';
  return sha.substring(0, 7);
}

const LOG_COLUMNS: ColumnsType<MirrorLog> = [
  {
    title: 'Log Type',
    dataIndex: 'log_type',
    key: 'log_type',
    render: (logType: string) => <Tag color={LOG_TAG_COLORS[logType] ?? 'default'}>{logType}</Tag>,
  },
  {
    title: 'Status',
    key: 'status',
    render: (_: unknown, record: MirrorLog) => (
      <StatusChip
        statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
        statusText={record.status_text}
      />
    ),
  },
  {
    title: 'Started At',
    dataIndex: 'started_at',
    key: 'started_at',
    render: (date: string) => formatDate(date),
  },
  {
    title: 'Duration',
    key: 'duration',
    render: (_: unknown, record: MirrorLog) => formatDuration(record.duration_ms),
  },
  {
    title: 'Source Commit',
    dataIndex: 'source_commit_sha',
    key: 'source_commit_sha',
    render: (sha: string) => <Typography.Text code>{shortSha(sha)}</Typography.Text>,
  },
  {
    title: 'Commits Behind',
    dataIndex: 'commits_behind',
    key: 'commits_behind',
    render: (val: number | undefined) =>
      val !== undefined && val !== null ? <Tag color={val > 0 ? 'red' : 'green'}>{val}</Tag> : '—',
  },
  {
    title: 'GitLab Pipeline',
    key: 'pipeline',
    render: (_: unknown, record: MirrorLog) =>
      record.gitlab_pipeline_url ? (
        <Tooltip title={`Pipeline #${record.gitlab_pipeline_id}`}>
          <Button
            size="small"
            type="link"
            icon={<LinkOutlined />}
            href={record.gitlab_pipeline_url}
            target="_blank"
            rel="noopener noreferrer"
          />
        </Tooltip>
      ) : (
        '—'
      ),
  },
  {
    title: 'Triggered By',
    dataIndex: 'triggered_by',
    key: 'triggered_by',
    render: (val: string | undefined) => val ?? '—',
  },
];

const MirrorProcessPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const mirrorId = Number(id);

  const [activeTab, setActiveTab] = useState<string>('process');

  // Fetch mirror detail
  const {
    data: mirror,
    isLoading: mirrorLoading,
    isError: mirrorError,
  } = useGetMirrorDetailQuery(mirrorId, { skip: isNaN(mirrorId) });

  // Logs tab state
  const [logTypeFilter, setLogTypeFilter] = useState<string>('');
  const [logStatusFilter, setLogStatusFilter] = useState<number>(-1);
  const [logPage, setLogPage] = useState(1);
  const [logPageSize, setLogPageSize] = useState(10);

  // Fetch logs for Logs tab
  const logsParams = {
    mirror_id: mirrorId,
    log_type: logTypeFilter || undefined,
    limit: logPageSize,
    offset: (logPage - 1) * logPageSize,
  };
  const {
    data: allLogs = [],
    isLoading: logsLoading,
    isError: logsError,
  } = useGetMirrorLogsV2Query(logsParams, {
    skip: isNaN(mirrorId),
  });

  // Mutations
  const [triggerSync, { isLoading: syncLoading }] = useTriggerMirrorSyncMutation();
  const [triggerFreshness, { isLoading: freshnessLoading }] = useTriggerFreshnessCheckMutation();

  const handleSync = async () => {
    try {
      await triggerSync(mirrorId).unwrap();
      message.success('Sync triggered');
    } catch {
      // error handled by RTK Query
    }
  };

  const handleFreshness = async () => {
    try {
      await triggerFreshness(mirrorId).unwrap();
      message.success('Freshness check triggered');
    } catch {
      // error handled by RTK Query
    }
  };

  // Loading state
  if (mirrorLoading) {
    return (
      <Flex justify="center" style={{ padding: '40px 0' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  // Error state
  if (mirrorError || !mirror) {
    return (
      <Alert
        message="Failed to load mirror"
        description="Please check the mirror ID and try again."
        type="error"
        showIcon
      />
    );
  }

  const sourceRepo = mirror.source_repository;
  const syncGroup = mirror.sync_group;
  const pipeline = syncGroup?.pipeline;

  // Recent logs from mirror detail for Process tab
  const recentLogs = (mirror.mirror_logs ?? []).slice(0, 10);

  // ── Process tab ──────────────────────────────────────────────────────────
  const processTab = (
    <Flex vertical gap={16}>
      {/* Mirror overview card */}
      <Card title="Mirror Overview" size="small">
        <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
          <Descriptions.Item label="Source">
            <Space>
              {sourceRepo ? (
                <>
                  <Button
                    type="link"
                    size="small"
                    icon={<GithubOutlined />}
                    href={sourceRepo.web_url ?? undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ padding: 0 }}
                  >
                    {sourceRepo.full_name}
                  </Button>
                </>
              ) : (
                <Typography.Text>{mirror.source_repository_id}</Typography.Text>
              )}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="Target">
            <Flex vertical>
              <Typography.Text strong>{mirror.target_gitlab_name ?? '—'}</Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {mirror.target_path}
              </Typography.Text>
              {mirror.target_web_url && (
                <Button
                  type="link"
                  size="small"
                  icon={<GitlabOutlined />}
                  href={mirror.target_web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ padding: 0, fontSize: 12 }}
                >
                  Open in GitLab
                </Button>
              )}
            </Flex>
          </Descriptions.Item>
          <Descriptions.Item label="Sync Group">
            {syncGroup?.name ?? mirror.sync_group_id}
          </Descriptions.Item>
          <Descriptions.Item label="Pipeline">
            {pipeline ? (
              <Typography.Text>
                {pipeline.name}
                {pipeline.ref ? ` (${pipeline.ref})` : ''}
              </Typography.Text>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Last Sync">
            <Flex gap={8} align="center">
              <Typography.Text>
                {mirror.last_sync_at ? new Date(mirror.last_sync_at).toLocaleString() : '—'}
              </Typography.Text>
              {mirror.last_sync_status && (
                <StatusChip
                  statusFlag={mirror.status_flag as 0 | 1 | 2 | 3 | 4}
                  statusText={mirror.last_sync_status}
                />
              )}
            </Flex>
          </Descriptions.Item>
          <Descriptions.Item label="Last Known Commit">
            <Flex vertical>
              <Typography.Text code>{shortSha(mirror.last_known_commit_sha)}</Typography.Text>
              {mirror.last_known_commit_date && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {new Date(mirror.last_known_commit_date).toLocaleString()}
                </Typography.Text>
              )}
              {mirror.last_known_commit_author && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  by {mirror.last_known_commit_author}
                </Typography.Text>
              )}
            </Flex>
          </Descriptions.Item>
          <Descriptions.Item label="Diverged Commits">
            <Tag color={(mirror.target_diverged_commits ?? 0) > 0 ? 'red' : 'green'}>
              {mirror.target_diverged_commits ?? 0}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Action buttons */}
      <Flex gap={8} wrap="wrap">
        <PermissionGate permission="mirrors:sync">
          <Tooltip title="Trigger sync via GitLab pipeline">
            <Button icon={<SyncOutlined />} loading={syncLoading} onClick={handleSync}>
              Trigger Sync
            </Button>
          </Tooltip>
        </PermissionGate>
        <PermissionGate permission="mirrors:sync">
          <Tooltip title="Check freshness of the mirror">
            <Button
              icon={<CheckCircleOutlined />}
              loading={freshnessLoading}
              onClick={handleFreshness}
            >
              Freshness Check
            </Button>
          </Tooltip>
        </PermissionGate>
        <PermissionGate permission="mirrors:sync">
          <Tooltip title="Run integrity check">
            <Button icon={<SafetyCertificateOutlined />}>Integrity Check</Button>
          </Tooltip>
        </PermissionGate>
      </Flex>

      {/* Recent logs table */}
      <Card title={`Recent Logs (${recentLogs.length})`} size="small">
        <Table
          columns={LOG_COLUMNS}
          dataSource={recentLogs}
          rowKey="id"
          pagination={false}
          size="small"
          locale={{ emptyText: <Empty description="No logs yet" /> }}
        />
      </Card>
    </Flex>
  );

  // ── Configuration tab ────────────────────────────────────────────────────
  const configTab = (
    <Flex vertical gap={16}>
      {/* Source Repository card */}
      <Card title="Source Repository" size="small">
        <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
          <Descriptions.Item label="Full Name">{sourceRepo?.full_name ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="Web URL">
            {sourceRepo?.web_url ? (
              <Button
                type="link"
                size="small"
                icon={<LinkOutlined />}
                href={sourceRepo.web_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ padding: 0 }}
              >
                {sourceRepo.web_url}
              </Button>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Archived">
            {sourceRepo?.is_archived ? <Tag color="warning">Yes — repository is archived</Tag> : 'No'}
          </Descriptions.Item>
          <Descriptions.Item label="Default Branch">
            <Typography.Text code>{sourceRepo?.default_branch ?? '—'}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Description" span={2}>
            {sourceRepo?.description ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="License">
            {sourceRepo?.license_spdx ? <Tag>{sourceRepo.license_spdx}</Tag> : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Language">
            {sourceRepo?.language ? <Tag>{sourceRepo.language}</Tag> : '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Target card */}
      <Card title="Target" size="small">
        <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
          <Descriptions.Item label="Target Namespace">{mirror.target_namespace}</Descriptions.Item>
          <Descriptions.Item label="Target Project Name">
            {mirror.target_project_name}
          </Descriptions.Item>
          <Descriptions.Item label="Target Project ID">
            {mirror.target_project_id ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Target Path">
            <Typography.Text code>{mirror.target_path}</Typography.Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Sync Group card */}
      <Card title="Sync Group" size="small">
        <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
          <Descriptions.Item label="Name">{syncGroup?.name ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="Sync Cron">
            {syncGroup?.sync_cron ? (
              <Typography.Text code>{syncGroup.sync_cron}</Typography.Text>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Freshness Cron">
            {syncGroup?.freshness_cron ? (
              <Typography.Text code>{syncGroup.freshness_cron}</Typography.Text>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Sync Concurrency">
            {syncGroup?.sync_concurrency ?? '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Pipeline card */}
      <Card title="Pipeline" size="small">
        <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
          <Descriptions.Item label="Name">{pipeline?.name ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="GitLab Instance">
            {pipeline?.gitlab_instance?.name ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Ref">
            {pipeline?.ref ? <Typography.Text code>{pipeline.ref}</Typography.Text> : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Is Default">
            {pipeline?.is_default ? <Tag color="blue">Yes</Tag> : 'No'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Import status */}
      <Card title="Import Status" size="small">
        <Flex align="center" gap={8}>
          <Typography.Text>Import Status:</Typography.Text>
          {mirror.is_imported ? (
            <Tag color="green">Imported</Tag>
          ) : (
            <Tag color="default">Not Imported</Tag>
          )}
        </Flex>
      </Card>

      {/* Edit button */}
      <Flex>
        <PermissionGate permission="mirrors:write">
          <Tooltip title="Edit mirror configuration">
            <Button icon={<EditOutlined />} disabled>
              Edit Config
            </Button>
          </Tooltip>
        </PermissionGate>
      </Flex>
    </Flex>
  );

  // ── Logs tab ─────────────────────────────────────────────────────────────
  const logsTab = (
    <Flex vertical gap={16}>
      {/* Filters */}
      <Card size="small">
        <Flex gap={12} wrap="wrap">
          <Select
            style={{ width: 150 }}
            value={logTypeFilter}
            onChange={(v) => {
              setLogTypeFilter(v);
              setLogPage(1);
            }}
            options={LOG_TYPE_OPTIONS}
          />
          <Select
            style={{ width: 150 }}
            value={logStatusFilter}
            onChange={(v) => {
              setLogStatusFilter(v);
              setLogPage(1);
            }}
            options={STATUS_OPTIONS}
          />
        </Flex>
      </Card>

      {/* Logs table */}
      <Card>
        {logsLoading && (
          <Flex justify="center" style={{ padding: '40px 0' }}>
            <Spin size="large" />
          </Flex>
        )}
        {logsError && (
          <Alert
            message="Failed to load logs"
            description="Please try again later."
            type="error"
            showIcon
          />
        )}
        {!logsLoading && !logsError && (
          <Table
            columns={LOG_COLUMNS}
            dataSource={allLogs}
            rowKey="id"
            pagination={{
              current: logPage,
              pageSize: logPageSize,
              showSizeChanger: true,
              pageSizeOptions: PAGE_SIZE_OPTIONS,
              onChange: (p, ps) => {
                setLogPage(p);
                setLogPageSize(ps);
              },
            }}
            expandable={{
              expandedRowRender: (record: MirrorLog) => (
                <pre
                  style={{
                    maxHeight: 300,
                    overflow: 'auto',
                    fontSize: 12,
                    padding: 8,
                    background: '#fafafa',
                    borderRadius: 4,
                  }}
                >
                  {JSON.stringify(record.details ?? record.details_json ?? {}, null, 2)}
                </pre>
              ),
              rowExpandable: (record: MirrorLog) => !!(record.details || record.details_json),
            }}
            locale={{ emptyText: <Empty description="No logs found" /> }}
          />
        )}
      </Card>
    </Flex>
  );

  // ── Tab items ────────────────────────────────────────────────────────────
  const tabItems = [
    {
      key: 'process',
      label: 'Process',
      children: processTab,
    },
    {
      key: 'configuration',
      label: 'Configuration',
      children: configTab,
    },
    {
      key: 'logs',
      label: 'Logs',
      children: logsTab,
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Breadcrumbs ─────────────────────────────────────────────────────── */}
      <Breadcrumb
        items={[
          { title: 'Git Mirroring', onClick: () => navigate('/git-mirroring/mirrors') },
          { title: 'Mirrors', onClick: () => navigate('/git-mirroring/mirrors') },
          { title: sourceRepo?.name ?? `Mirror #${mirrorId}` },
        ]}
      />

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Space>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Mirror Process — {sourceRepo?.full_name ?? `Mirror #${mirrorId}`}
          </Typography.Title>
        </Space>
        <StatusChip
          statusFlag={mirror.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={mirror.status_text}
        />
      </Flex>

      {/* ── Tabs ────────────────────────────────────────────────────────────── */}
      <Card>
        <Tabs activeKey={activeTab} onChange={(key) => setActiveTab(key)} items={tabItems} />
      </Card>
    </Flex>
  );
};

export default MirrorProcessPage;
