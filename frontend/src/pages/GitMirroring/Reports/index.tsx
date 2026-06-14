/**
 * @file Reports/index.tsx
 * @description Git Mirroring Reports page with 5 sub-tabs:
 *              Duplicates, Storage, Status, Syncs, Bulk Operations.
 * @dependencies antd, @reduxjs/toolkit, react-router
 * @relatedFiles ../../../store/api.ts, ../../../types/index.ts, ../../../components/StatusChip.tsx
 */

import { useState, useMemo } from 'react';
import {
  Tabs,
  Table,
  Button,
  Alert,
  Card,
  Space,
  Flex,
  Typography,
  Empty,
  Select,
  DatePicker,
  Progress,
  Tag,
  Radio,
  message,
  Divider,
} from 'antd';
import {
  DownloadOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { StatusChip } from '../../../components/StatusChip';
import {
  useGetDuplicatesReportQuery,
  useGetStorageReportQuery,
  useRefreshStorageReportMutation,
  useGetStatusReportQuery,
  useGetSyncsReportQuery,
  useBulkReassignSyncGroupMutation,
  useBulkChangeTargetGitlabMutation,
  useBulkApplyPipelineMutation,
  useGetMirrorsQuery,
  useGetSyncGroupsQuery,
  useGetPipelineConfigsQuery,
} from '../../../store/api';
import type {
  DuplicateGroup,
  DuplicateMirrorItem,
  MirrorStorageItem,
  StorageSummary,
  StatusCountItem,
  MirrorStatusItem,
  DailySyncsItem,
  SyncGroupSyncsItem,
  TopSyncMirrorItem,
  BulkOperationResultItem,
  Mirror,
} from '../../../types';

const { RangePicker } = DatePicker;
const { Text, Title } = Typography;

// ─── Constants ────────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const STATUS_COLORS: Record<number, string> = {
  0: '#52c41a', // OK — green
  1: '#ff4d4f', // Failed — red
  2: '#faad14', // Warning — orange
  3: '#1677ff', // In Progress — blue
  4: '#d9d9d9', // Pending — grey
};

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return 'N/A';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const idx = Math.min(i, units.length - 1);
  return `${(bytes / Math.pow(k, idx)).toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

function downloadFile(url: string, filename: string) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function exportUrl(reportType: string, format: 'csv' | 'json', params?: Record<string, string>): string {
  const url = new URL(`${BASE_URL}/api/reports/${reportType}/export`);
  url.searchParams.set('format', format);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v) url.searchParams.set(k, v);
    });
  }
  return url.toString();
}

// ─── Donut Chart (CSS/SVG) ────────────────────────────────────────────────

function DonutChart({ items, total }: { items: StatusCountItem[]; total: number }) {
  const radius = 80;
  const center = 100;
  const circumference = 2 * Math.PI * radius;

  let currentOffset = 0;

  const segments = items.map((item) => {
    const fraction = total > 0 ? item.count / total : 0;
    const dashLength = fraction * circumference;
    const dashOffset = -currentOffset;
    currentOffset += dashLength;

    return {
      ...item,
      fraction,
      dashLength,
      dashOffset,
    };
  });

  return (
    <Flex vertical align="center" gap={8}>
      <svg width={200} height={200} viewBox="0 0 200 200">
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#f0f0f0"
          strokeWidth={24}
        />
        {segments.map((seg) => (
          <circle
            key={seg.status_flag}
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={STATUS_COLORS[seg.status_flag] ?? '#d9d9d9'}
            strokeWidth={24}
            strokeDasharray={`${seg.dashLength} ${circumference - seg.dashLength}`}
            strokeDashoffset={seg.dashOffset}
            transform="rotate(-90 100 100)"
            style={{ transition: 'stroke-dasharray 0.3s' }}
          />
        ))}
        <text x={center} y={center - 8} textAnchor="middle" fontSize={28} fontWeight="bold" fill="#333">
          {total}
        </text>
        <text x={center} y={center + 16} textAnchor="middle" fontSize={12} fill="#888">
          mirrors
        </text>
      </svg>
      {/* Legend */}
      <Flex gap={12} wrap="wrap" justify="center">
        {items.map((item) => (
          <Space key={item.status_flag} size={4}>
            <span
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: STATUS_COLORS[item.status_flag] ?? '#d9d9d9',
              }}
            />
            <Text style={{ fontSize: 12 }}>
              {item.label} ({item.count})
            </Text>
          </Space>
        ))}
      </Flex>
    </Flex>
  );
}

// ─── Tab 1: Duplicates ────────────────────────────────────────────────────

function DuplicatesTab() {
  const { data, isLoading } = useGetDuplicatesReportQuery();

  const groupColumns: ColumnsType<DuplicateGroup> = [
    { title: 'Source URL', dataIndex: 'source_url', key: 'source_url', ellipsis: true },
    {
      title: 'Mirrors',
      dataIndex: 'mirror_count',
      key: 'mirror_count',
      width: 100,
      align: 'center',
    },
  ];

  const mirrorColumns: ColumnsType<DuplicateMirrorItem> = [
    { title: 'Mirror ID', dataIndex: 'mirror_id', key: 'mirror_id', width: 100 },
    { title: 'Target GitLab', dataIndex: 'target_gitlab_instance_name', key: 'target_gitlab_instance_name', ellipsis: true },
    { title: 'Target Path', dataIndex: 'target_path', key: 'target_path', ellipsis: true },
    {
      title: 'Status',
      dataIndex: 'status_flag',
      key: 'status_flag',
      width: 120,
      render: (flag: number, record: { status_text?: string | null }) => (
        <StatusChip status={flag} statusText={record.status_text} />
      ),
    },
    { title: 'Sync Group', dataIndex: 'sync_group_name', key: 'sync_group_name', ellipsis: true },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '—'),
    },
  ];

  if (!data || data.groups.length === 0) {
    return (
      <Flex vertical gap={16}>
        <Alert
          type="success"
          showIcon
          icon={<CheckCircleOutlined />}
          title="Дубликаты не обнаружены"
          description="Все зеркала уникальны — каждому source URL соответствует только одно зеркало."
        />
      </Flex>
    );
  }

  return (
    <Flex vertical gap={16}>
      <Alert
        type="warning"
        showIcon
        title={data.warning}
      />
      <Space>
        <Button
          icon={<DownloadOutlined />}
          onClick={() => downloadFile(exportUrl('duplicates', 'csv'), 'duplicates_report.csv')}
        >
          Export CSV
        </Button>
        <Button
          icon={<DownloadOutlined />}
          onClick={() => downloadFile(exportUrl('duplicates', 'json'), 'duplicates_report.json')}
        >
          Export JSON
        </Button>
      </Space>
      <Table
        columns={groupColumns}
        dataSource={data.groups}
        rowKey="source_url"
        loading={isLoading}
        expandable={{
          expandedRowRender: (group: DuplicateGroup) => (
            <Table
              columns={mirrorColumns}
              dataSource={group.mirrors}
              rowKey="mirror_id"
              pagination={false}
              size="small"
            />
          ),
          rowExpandable: (group: DuplicateGroup) => group.mirrors.length > 0,
        }}
      />
    </Flex>
  );
}

// ─── Tab 2: Storage ───────────────────────────────────────────────────────

function StorageTab() {
  const { data, isLoading } = useGetStorageReportQuery();
  const [refreshStorage, { isLoading: isRefreshing }] = useRefreshStorageReportMutation();

  const handleRefresh = async () => {
    try {
      await refreshStorage().unwrap();
      message.success('Storage data refreshed');
    } catch {
      message.error('Failed to refresh storage data');
    }
  };

  const columns: ColumnsType<MirrorStorageItem> = [
    {
      title: 'Mirror',
      dataIndex: 'mirror_id',
      key: 'mirror_id',
      width: 80,
    },
    {
      title: 'Source URL',
      dataIndex: 'source_url',
      key: 'source_url',
      ellipsis: true,
    },
    {
      title: 'Target GitLab',
      dataIndex: 'target_gitlab_instance_name',
      key: 'target_gitlab_instance_name',
      ellipsis: true,
    },
    {
      title: 'Repo Size',
      dataIndex: 'repo_size_bytes',
      key: 'repo_size_bytes',
      width: 100,
      align: 'right',
      render: (v: number | null, record: MirrorStorageItem) => {
        if (record.error)
          return <Tag color="orange">N/A</Tag>;
        return formatBytes(v);
      },
    },
    {
      title: 'History Size',
      dataIndex: 'history_size_bytes',
      key: 'history_size_bytes',
      width: 110,
      align: 'right',
      render: (v: number | null, record: MirrorStorageItem) => {
        if (record.error)
          return <Tag color="orange">N/A</Tag>;
        return formatBytes(v);
      },
    },
    {
      title: 'Total Size',
      dataIndex: 'total_size_bytes',
      key: 'total_size_bytes',
      width: 110,
      align: 'right',
      render: (v: number | null, record: MirrorStorageItem) => {
        if (record.error)
          return <Tag color="orange">N/A</Tag>;
        return <Text strong>{formatBytes(v)}</Text>;
      },
    },
  ];

  const summaryColumns: ColumnsType<StorageSummary> = [
    { title: 'Group', dataIndex: 'key', key: 'key' },
    {
      title: 'Repo Size',
      dataIndex: 'repo_size_bytes',
      key: 'repo_size_bytes',
      align: 'right',
      render: (v: number) => formatBytes(v),
    },
    {
      title: 'History Size',
      dataIndex: 'history_size_bytes',
      key: 'history_size_bytes',
      align: 'right',
      render: (v: number) => formatBytes(v),
    },
    {
      title: 'Total Size',
      dataIndex: 'total_size_bytes',
      key: 'total_size_bytes',
      align: 'right',
      render: (v: number) => <Text strong>{formatBytes(v)}</Text>,
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* Header with timestamp and refresh */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Space>
          {data?.collected_at ? (
            <Text type="secondary">
              Данные от {dayjs(data.collected_at).format('DD.MM.YYYY HH:mm')}
            </Text>
          ) : (
            <Text type="secondary">Данные ещё не собраны</Text>
          )}
          {data?.is_stale && <Tag color="warning">Устарели</Tag>}
          {data?.collection_status === 'in_progress' && <Tag color="processing">Сбор данных...</Tag>}
        </Space>
        <Button
          icon={<ReloadOutlined />}
          onClick={handleRefresh}
          loading={isRefreshing}
        >
          Refresh
        </Button>
      </Flex>

      {/* Progress bar when collecting */}
      {data?.collection_status === 'in_progress' && (
        <Progress percent={100} status="active" strokeColor="#1677ff" />
      )}

      {/* Table */}
      <Table
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="mirror_id"
        loading={isLoading}
        pagination={{ pageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
      />

      {/* Export */}
      <Space>
        <Button
          icon={<DownloadOutlined />}
          onClick={() => downloadFile(exportUrl('storage', 'csv'), 'storage_report.csv')}
        >
          Export CSV
        </Button>
        <Button
          icon={<DownloadOutlined />}
          onClick={() => downloadFile(exportUrl('storage', 'json'), 'storage_report.json')}
        >
          Export JSON
        </Button>
      </Space>

      {/* Summary */}
      {data && (
        <Flex vertical gap={16}>
          <Divider />

          {/* By GitLab Instance */}
          {data.by_gitlab_instance.length > 0 && (
            <Card title="По GitLab Instance" size="small">
              <Table
                columns={summaryColumns}
                dataSource={data.by_gitlab_instance}
                rowKey="key"
                pagination={false}
                size="small"
              />
            </Card>
          )}

          {/* By Sync Group */}
          {data.by_sync_group.length > 0 && (
            <Card title="По Sync Group" size="small">
              <Table
                columns={summaryColumns}
                dataSource={data.by_sync_group}
                rowKey="key"
                pagination={false}
                size="small"
              />
            </Card>
          )}

          {/* Grand Total */}
          {data.grand_total && (
            <Card size="small">
              <Flex justify="space-between" align="center">
                <Title level={5} style={{ margin: 0 }}>
                  Общий итог
                </Title>
                <Space size="large">
                  <Text>Repo: <Text strong>{formatBytes(data.grand_total.repo_size_bytes)}</Text></Text>
                  <Text>History: <Text strong>{formatBytes(data.grand_total.history_size_bytes)}</Text></Text>
                  <Text style={{ fontSize: 18 }}>
                    Total: <Text strong style={{ fontSize: 18 }}>{formatBytes(data.grand_total.total_size_bytes)}</Text>
                  </Text>
                </Space>
              </Flex>
            </Card>
          )}
        </Flex>
      )}

      {!data?.items?.length && !isLoading && (
        <Empty description="No storage data available" />
      )}
    </Flex>
  );
}

// ─── Tab 3: Status ────────────────────────────────────────────────────────

function StatusTab() {
  const [trendDays, setTrendDays] = useState<number>(30);
  const { data, isLoading } = useGetStatusReportQuery(
    trendDays > 0 ? { trend_days: trendDays } : undefined,
  );

  const mirrorColumns: ColumnsType<MirrorStatusItem> = [
    { title: 'Mirror ID', dataIndex: 'mirror_id', key: 'mirror_id', width: 100 },
    { title: 'Source URL', dataIndex: 'source_url', key: 'source_url', ellipsis: true },
    {
      title: 'Status',
      dataIndex: 'status_flag',
      key: 'status_flag',
      width: 120,
      render: (flag: number, record: MirrorStatusItem) => (
        <StatusChip status={flag} statusText={record.status_text} />
      ),
    },
    { title: 'Target Path', dataIndex: 'target_path', key: 'target_path', ellipsis: true },
    { title: 'Sync Group', dataIndex: 'sync_group_name', key: 'sync_group_name', ellipsis: true },
  ];

  const statusTableColumns: ColumnsType<StatusCountItem> = [
    {
      title: 'Status',
      dataIndex: 'label',
      key: 'label',
      width: 150,
      render: (_: string, record: StatusCountItem) => (
        <Space>
          <span
            style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: STATUS_COLORS[record.status_flag] ?? '#d9d9d9',
            }}
          />
          <Text>{record.label}</Text>
        </Space>
      ),
    },
    {
      title: 'Count',
      dataIndex: 'count',
      key: 'count',
      width: 100,
      align: 'center',
    },
    {
      title: '% of Total',
      key: 'percentage',
      width: 120,
      align: 'center',
      render: (_: unknown, record: StatusCountItem) =>
        data && data.total_mirrors > 0
          ? `${((record.count / data.total_mirrors) * 100).toFixed(1)}%`
          : '—',
    },
  ];

  // Map status_flag → mirror list
  const mirrorsByStatus: Record<number, MirrorStatusItem[]> = {
    0: data?.ok_mirrors ?? [],
    1: data?.failed_mirrors ?? [],
    2: data?.warning_mirrors ?? [],
    3: data?.in_progress_mirrors ?? [],
    4: data?.pending_mirrors ?? [],
  };

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Space>
          <Text>Trend period:</Text>
          <Select
            value={trendDays}
            onChange={setTrendDays}
            style={{ width: 120 }}
            options={[
              { value: 0, label: 'All time' },
              { value: 7, label: '7 days' },
              { value: 30, label: '30 days' },
              { value: 90, label: '90 days' },
            ]}
          />
        </Space>
        <Space>
          <Button
            icon={<DownloadOutlined />}
            onClick={() =>
              downloadFile(
                exportUrl('status', 'csv', trendDays > 0 ? { trend_days: String(trendDays) } : {}),
                'status_report.csv',
              )
            }
          >
            Export CSV
          </Button>
          <Button
            icon={<DownloadOutlined />}
            onClick={() =>
              downloadFile(
                exportUrl('status', 'json', trendDays > 0 ? { trend_days: String(trendDays) } : {}),
                'status_report.json',
              )
            }
          >
            Export JSON
          </Button>
        </Space>
      </Flex>

      {data && (
        <Flex gap={24} wrap="wrap" align="flex-start">
          <Card size="small">
            <DonutChart items={data.status_counts} total={data.total_mirrors} />
          </Card>
          <Card size="small" style={{ flex: 1, minWidth: 300 }}>
            <Table
              columns={statusTableColumns}
              dataSource={data.status_counts}
              rowKey="status_flag"
              pagination={false}
              size="small"
              loading={isLoading}
              expandable={{
                expandedRowRender: (record: StatusCountItem) => (
                  <Table
                    columns={mirrorColumns}
                    dataSource={mirrorsByStatus[record.status_flag] ?? []}
                    rowKey="mirror_id"
                    pagination={false}
                    size="small"
                  />
                ),
                rowExpandable: (record: StatusCountItem) =>
                  (mirrorsByStatus[record.status_flag] ?? []).length > 0,
              }}
            />
          </Card>
        </Flex>
      )}

      {!data && !isLoading && <Empty description="No status data available" />}
    </Flex>
  );
}

// ─── Tab 4: Syncs ─────────────────────────────────────────────────────────

function SyncsTab() {
  const [periodStart, setPeriodStart] = useState<string>(
    dayjs().subtract(30, 'day').format('YYYY-MM-DD'),
  );
  const [periodEnd, setPeriodEnd] = useState<string>(dayjs().format('YYYY-MM-DD'));

  const { data, isLoading } = useGetSyncsReportQuery(
    periodStart && periodEnd
      ? { period_start: periodStart, period_end: periodEnd }
      : undefined,
  );

  const dailyColumns: ColumnsType<DailySyncsItem> = [
    { title: 'Date', dataIndex: 'date', key: 'date', width: 120 },
    { title: 'Total', dataIndex: 'total', key: 'total', align: 'center', width: 80 },
    {
      title: 'Success',
      dataIndex: 'successful',
      key: 'successful',
      align: 'center',
      width: 90,
      render: (v: number) => <Text style={{ color: '#52c41a' }}>{v}</Text>,
    },
    {
      title: 'Failed',
      dataIndex: 'failed',
      key: 'failed',
      align: 'center',
      width: 80,
      render: (v: number) => (v > 0 ? <Text style={{ color: '#ff4d4f' }}>{v}</Text> : v),
    },
    {
      title: 'Stale',
      dataIndex: 'stale',
      key: 'stale',
      align: 'center',
      width: 80,
      render: (v: number) => (v > 0 ? <Text style={{ color: '#faad14' }}>{v}</Text> : v),
    },
  ];

  const syncGroupColumns: ColumnsType<SyncGroupSyncsItem> = [
    { title: 'Sync Group', dataIndex: 'sync_group_name', key: 'sync_group_name' },
    { title: 'Total', dataIndex: 'total', key: 'total', align: 'center', width: 80 },
    {
      title: 'Success',
      dataIndex: 'successful',
      key: 'successful',
      align: 'center',
      width: 90,
      render: (v: number) => <Text style={{ color: '#52c41a' }}>{v}</Text>,
    },
    {
      title: 'Failed',
      dataIndex: 'failed',
      key: 'failed',
      align: 'center',
      width: 80,
      render: (v: number) => (v > 0 ? <Text style={{ color: '#ff4d4f' }}>{v}</Text> : v),
    },
    {
      title: 'Stale',
      dataIndex: 'stale',
      key: 'stale',
      align: 'center',
      width: 80,
      render: (v: number) => (v > 0 ? <Text style={{ color: '#faad14' }}>{v}</Text> : v),
    },
  ];

  const topBySyncsColumns: ColumnsType<TopSyncMirrorItem> = [
    { title: 'Mirror ID', dataIndex: 'mirror_id', key: 'mirror_id', width: 100 },
    { title: 'Source URL', dataIndex: 'source_url', key: 'source_url', ellipsis: true },
    { title: 'Syncs count', dataIndex: 'count', key: 'count', align: 'center', width: 120 },
  ];

  const topByErrorsColumns: ColumnsType<TopSyncMirrorItem> = [
    { title: 'Mirror ID', dataIndex: 'mirror_id', key: 'mirror_id', width: 100 },
    { title: 'Source URL', dataIndex: 'source_url', key: 'source_url', ellipsis: true },
    { title: 'Errors count', dataIndex: 'count', key: 'count', align: 'center', width: 120 },
  ];

  return (
    <Flex vertical gap={16}>
      {/* Period Picker */}
      <Flex gap={12} align="center" wrap="wrap">
        <Text strong>Period:</Text>
        <RangePicker
          value={[dayjs(periodStart), dayjs(periodEnd)]}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) {
              setPeriodStart(dates[0].format('YYYY-MM-DD'));
              setPeriodEnd(dates[1].format('YYYY-MM-DD'));
            }
          }}
          presets={[
            { label: 'Today', value: [dayjs(), dayjs()] },
            { label: 'Last 7 Days', value: [dayjs().subtract(7, 'day'), dayjs()] },
            { label: 'Last 30 Days', value: [dayjs().subtract(30, 'day'), dayjs()] },
          ]}
        />
      </Flex>

      {/* Export */}
      <Space>
        <Button
          icon={<DownloadOutlined />}
          onClick={() =>
            downloadFile(
              exportUrl('syncs', 'csv', { period_start: periodStart, period_end: periodEnd }),
              'syncs_report.csv',
            )
          }
        >
          Export CSV
        </Button>
        <Button
          icon={<DownloadOutlined />}
          onClick={() =>
            downloadFile(
              exportUrl('syncs', 'json', { period_start: periodStart, period_end: periodEnd }),
              'syncs_report.json',
            )
          }
        >
          Export JSON
        </Button>
      </Space>

      {data && (
        <Flex vertical gap={16}>
          {/* Daily Table */}
          <Card title="По дням" size="small">
            <Table
              columns={dailyColumns}
              dataSource={data.daily}
              rowKey="date"
              pagination={false}
              size="small"
              loading={isLoading}
            />
          </Card>

          {/* By Sync Group */}
          {data.by_sync_group.length > 0 && (
            <Card title="По Sync Group" size="small">
              <Table
                columns={syncGroupColumns}
                dataSource={data.by_sync_group}
                rowKey="sync_group_name"
                pagination={false}
                size="small"
                loading={isLoading}
              />
            </Card>
          )}

          {/* Top 10 by syncs */}
          {data.top_by_syncs.length > 0 && (
            <Card title="Топ-10 по синхронизациям" size="small">
              <Table
                columns={topBySyncsColumns}
                dataSource={data.top_by_syncs}
                rowKey="mirror_id"
                pagination={false}
                size="small"
              />
            </Card>
          )}

          {/* Top 10 by errors */}
          {data.top_by_errors.length > 0 && (
            <Card title="Топ-10 по ошибкам" size="small">
              <Table
                columns={topByErrorsColumns}
                dataSource={data.top_by_errors}
                rowKey="mirror_id"
                pagination={false}
                size="small"
              />
            </Card>
          )}
        </Flex>
      )}

      {!data && !isLoading && <Empty description="No syncs data available" />}
    </Flex>
  );
}

// ─── Tab 5: Bulk Operations ───────────────────────────────────────────────

function BulkOperationsTab() {
  const [selectedMirrorIds, setSelectedMirrorIds] = useState<number[]>([]);
  const [operationType, setOperationType] = useState<string>('reassign-sync-group');
  const [targetSyncGroupId, setTargetSyncGroupId] = useState<number | null>(null);
  const [targetPipelineId, setTargetPipelineId] = useState<number | null>(null);
  const [results, setResults] = useState<BulkOperationResultItem[] | null>(null);

  const { data: mirrors, isLoading: mirrorsLoading } = useGetMirrorsQuery(
    { limit: 500 },
  );
  const { data: syncGroups, isLoading: syncGroupsLoading } = useGetSyncGroupsQuery();
  const { data: pipelineConfigs, isLoading: pipelinesLoading } = useGetPipelineConfigsQuery();

  const [reassignSyncGroup, { isLoading: reassigning }] = useBulkReassignSyncGroupMutation();
  const [changeTargetGitlab, { isLoading: changingGitlab }] = useBulkChangeTargetGitlabMutation();
  const [applyPipeline, { isLoading: applyingPipeline }] = useBulkApplyPipelineMutation();

  const isExecuting = reassigning || changingGitlab || applyingPipeline;

  const handleExecute = async () => {
    if (selectedMirrorIds.length === 0) {
      message.warning('Select at least one mirror');
      return;
    }

    try {
      let response;
      switch (operationType) {
        case 'reassign-sync-group':
          if (!targetSyncGroupId) {
            message.warning('Select a SyncGroup');
            return;
          }
          response = await reassignSyncGroup({
            mirror_ids: selectedMirrorIds,
            sync_group_id: targetSyncGroupId,
          }).unwrap();
          break;

        case 'change-target-gitlab':
          if (!targetSyncGroupId) {
            message.warning('Select a SyncGroup (target GitLab is determined by SyncGroup → Pipeline → GitLab Instance)');
            return;
          }
          response = await changeTargetGitlab({
            mirror_ids: selectedMirrorIds,
            sync_group_id: targetSyncGroupId,
          }).unwrap();
          break;

        case 'apply-pipeline':
          if (!targetPipelineId) {
            message.warning('Select a Pipeline');
            return;
          }
          response = await applyPipeline({
            mirror_ids: selectedMirrorIds,
            pipeline_id: targetPipelineId,
          }).unwrap();
          break;

        default:
          return;
      }

      setResults(response.results);
      if (response.failed > 0) {
        message.warning(`${response.succeeded} succeeded, ${response.failed} failed`);
      } else {
        message.success(`${response.succeeded} mirrors updated successfully`);
      }
    } catch {
      message.error('Operation failed');
    }
  };

  const resultColumns: ColumnsType<BulkOperationResultItem> = [
    { title: 'Mirror ID', dataIndex: 'mirror_id', key: 'mirror_id', width: 100 },
    {
      title: 'Result',
      dataIndex: 'success',
      key: 'success',
      width: 100,
      render: (success: boolean) =>
        success ? (
          <Tag color="success">Success</Tag>
        ) : (
          <Tag color="error">Failed</Tag>
        ),
    },
    {
      title: 'Message',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true,
      render: (msg: string | null) => msg || '—',
    },
  ];

  const mirrorOptions = useMemo(
    () =>
      (mirrors ?? []).map((m: Mirror) => ({
        label: `#${m.id} — ${m.source_repository?.full_name ?? m.target_path}`,
        value: m.id,
      })),
    [mirrors],
  );

  const syncGroupOptions = useMemo(
    () =>
      (syncGroups ?? []).map((sg) => ({
        label: sg.name,
        value: sg.id,
      })),
    [syncGroups],
  );

  const pipelineOptions = useMemo(
    () =>
      (pipelineConfigs ?? []).map((pc) => ({
        label: pc.name,
        value: pc.id,
      })),
    [pipelineConfigs],
  );

  return (
    <Flex vertical gap={16}>
      <Card title="Bulk Operations" size="small">
        <Flex vertical gap={16}>
          {/* Mirror Selection */}
          <Flex vertical gap={8}>
            <Text strong>Select Mirrors:</Text>
            <Select
              mode="multiple"
              style={{ width: '100%' }}
              placeholder="Search mirrors..."
              value={selectedMirrorIds}
              onChange={setSelectedMirrorIds}
              options={mirrorOptions}
              loading={mirrorsLoading}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              maxTagCount={5}
            />
          </Flex>

          {/* Operation Type */}
          <Flex vertical gap={8}>
            <Text strong>Operation:</Text>
            <Radio.Group
              value={operationType}
              onChange={(e) => {
                setOperationType(e.target.value);
                setResults(null);
              }}
            >
              <Radio.Button value="reassign-sync-group">Reassign SyncGroup</Radio.Button>
              <Radio.Button value="change-target-gitlab">Change Target GitLab</Radio.Button>
              <Radio.Button value="apply-pipeline">Apply Pipeline</Radio.Button>
            </Radio.Group>
          </Flex>

          {/* Target (depends on operation) */}
          {(operationType === 'reassign-sync-group' || operationType === 'change-target-gitlab') && (
            <Flex vertical gap={8}>
              <Text strong>
                {operationType === 'reassign-sync-group'
                  ? 'Target SyncGroup:'
                  : 'Target SyncGroup (with desired GitLab instance):'}
              </Text>
              <Select
                style={{ width: 400 }}
                placeholder="Select SyncGroup..."
                value={targetSyncGroupId}
                onChange={setTargetSyncGroupId}
                options={syncGroupOptions}
                loading={syncGroupsLoading}
              />
            </Flex>
          )}

          {operationType === 'apply-pipeline' && (
            <Flex vertical gap={8}>
              <Text strong>Target Pipeline:</Text>
              <Select
                style={{ width: 400 }}
                placeholder="Select Pipeline..."
                value={targetPipelineId}
                onChange={setTargetPipelineId}
                options={pipelineOptions}
                loading={pipelinesLoading}
              />
            </Flex>
          )}

          <Button
            type="primary"
            onClick={handleExecute}
            loading={isExecuting}
            disabled={selectedMirrorIds.length === 0}
          >
            Execute
          </Button>
        </Flex>
      </Card>

      {/* Results */}
      {results && (
        <Card title="Results" size="small">
          <Table
            columns={resultColumns}
            dataSource={results}
            rowKey="mirror_id"
            pagination={false}
            size="small"
          />
        </Card>
      )}
    </Flex>
  );
}

// ─── Main Reports Page ────────────────────────────────────────────────────

const TAB_ITEMS = [
  { key: 'duplicates', label: 'Duplicates', children: <DuplicatesTab /> },
  { key: 'storage', label: 'Storage', children: <StorageTab /> },
  { key: 'status', label: 'Status', children: <StatusTab /> },
  { key: 'syncs', label: 'Syncs', children: <SyncsTab /> },
  { key: 'bulk', label: 'Bulk Operations', children: <BulkOperationsTab /> },
];

export default function ReportsPage() {
  return (
    <Flex vertical gap={16}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        Git Mirroring Reports
      </Typography.Title>
      <Card>
        <Tabs defaultActiveKey="duplicates" items={TAB_ITEMS} />
      </Card>
    </Flex>
  );
}
