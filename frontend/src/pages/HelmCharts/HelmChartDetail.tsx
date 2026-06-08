/**
 * @file HelmChartDetail.tsx
 * @description Страница деталей Helm Chart: source info, версии, история синхронизации
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useParams, useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Spin,
  Divider,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import {
  useGetHelmChartQuery,
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
  useIndexHelmChartMutation,
} from '../../store/api';
import { HelmChartSourceDetail, HelmChartVersion, HelmSyncLog } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function HelmChartDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const chartId = Number(id);

  const { data: chart, isLoading } = useGetHelmChartQuery(chartId);
  const { data: versions = [] } = useGetHelmChartVersionsQuery(chartId);
  const { data: logs = [] } = useGetHelmChartLogsQuery(chartId);
  const [indexChart, { isLoading: indexing }] = useIndexHelmChartMutation();

  const c = chart as HelmChartSourceDetail | undefined;

  // ── Loading / Not Found ──────────────────────────────────────────────────
  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: 48 }}>
        <Spin size="large" />
      </Flex>
    );
  }
  if (!c) {
    return (
      <Flex vertical align="center" gap={16} style={{ padding: 48 }}>
        <Typography.Text type="secondary">Helm chart source not found</Typography.Text>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/helm-charts')}>
          Back to Helm Charts
        </Button>
      </Flex>
    );
  }

  // ── Versions Table Columns ───────────────────────────────────────────────
  const versionColumns: ColumnsType<HelmChartVersion> = [
    {
      title: 'Chart',
      key: 'chart',
      render: (_: unknown, record: HelmChartVersion) => (
        <Flex vertical>
          <Typography.Text strong>{record.chart_name}</Typography.Text>
          {record.description && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {record.description.length > 80
                ? record.description.slice(0, 80) + '…'
                : record.description}
            </Typography.Text>
          )}
        </Flex>
      ),
    },
    {
      title: 'Version',
      dataIndex: 'version',
      key: 'version',
      render: (val: string) => (
        <Typography.Text code style={{ fontSize: '0.8rem' }}>
          {val}
        </Typography.Text>
      ),
    },
    {
      title: 'App Version',
      dataIndex: 'app_version',
      key: 'app_version',
      render: (val: string | null) =>
        val ? (
          <Typography.Text code style={{ fontSize: '0.8rem' }}>
            {val}
          </Typography.Text>
        ) : (
          '—'
        ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: HelmChartVersion) => (
        <Flex align="center" gap={8}>
          <StatusChip
            statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
            statusText={record.status_text}
          />
          {record.is_synced && (
            <Typography.Text type="success" strong style={{ fontSize: 12 }}>
              ✓ Synced
            </Typography.Text>
          )}
        </Flex>
      ),
    },
  ];

  // ── Sync History Table Columns ───────────────────────────────────────────
  const logColumns: ColumnsType<HelmSyncLog> = [
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: 'Triggered By',
      dataIndex: 'triggered_by',
      key: 'triggered_by',
      render: (val: string | null) => val ?? '—',
    },
    {
      title: 'Pipeline',
      key: 'pipeline',
      render: (_: unknown, record: HelmSyncLog) =>
        record.pipeline_url ? (
          <Button
            size="small"
            type="link"
            icon={<LinkOutlined />}
            href={record.pipeline_url}
            target="_blank"
          >
            #{record.pipeline_id}
          </Button>
        ) : (
          (record.pipeline_id ?? '—')
        ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: HelmSyncLog) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: unknown, record: HelmSyncLog) => {
        if (record.started_at && record.finished_at) {
          const seconds = Math.round(
            (new Date(record.finished_at).getTime() - new Date(record.started_at).getTime()) / 1000,
          );
          return `${seconds}s`;
        }
        return '—';
      },
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex align="center" gap={12} wrap="wrap">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/helm-charts')}>
          Back
        </Button>
        <Typography.Title level={4} style={{ margin: 0, flex: 1 }}>
          {c.name}
        </Typography.Title>
        <Tooltip title={indexing ? 'Indexing…' : 'Re-index chart versions'}>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={() => indexChart(chartId)}
            loading={indexing}
          >
            Re-index
          </Button>
        </Tooltip>
        <Button
          icon={<LinkOutlined />}
          href={c.repo_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open Repo
        </Button>
      </Flex>

      {/* ── Info + Versions Cards ───────────────────────────────────────────── */}
      <Flex gap={16} wrap="wrap">
        {/* Source Info Card */}
        <Card title="Source Info" style={{ flex: '1 1 300px', minWidth: 280 }}>
          <Flex vertical gap={12}>
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Status
              </Typography.Text>
              <StatusChip
                statusFlag={c.status_flag as 0 | 1 | 2 | 3 | 4}
                statusText={c.status_text}
              />
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Repository URL
              </Typography.Text>
              <Typography.Text code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                {c.repo_url}
              </Typography.Text>
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Description
              </Typography.Text>
              <Typography.Text>{c.description ?? '—'}</Typography.Text>
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Last Synced
              </Typography.Text>
              <Typography.Text>
                {c.last_synced_at
                  ? new Date(c.last_synced_at).toLocaleString()
                  : 'Never'}
              </Typography.Text>
            </Flex>
            {c.gitlab_project_url && (
              <>
                <Divider style={{ margin: 0 }} />
                <Flex vertical>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    GitLab Project
                  </Typography.Text>
                  <Typography.Link href={c.gitlab_project_url} target="_blank" rel="noopener noreferrer">
                    {c.gitlab_project_id ?? c.gitlab_project_url}
                  </Typography.Link>
                </Flex>
              </>
            )}
          </Flex>
        </Card>

        {/* Chart Versions Card */}
        <Card
          title={`Chart Versions (${(versions as HelmChartVersion[]).length})`}
          style={{ flex: '2 1 500px', minWidth: 350 }}
        >
          <Table
            columns={versionColumns}
            dataSource={versions as HelmChartVersion[]}
            rowKey="id"
            size="small"
            pagination={false}
            scroll={{ y: 360 }}
            locale={{
              emptyText:
                'No versions indexed yet. Click "Re-index" to fetch chart versions.',
            }}
          />
        </Card>
      </Flex>

      {/* ── Sync History Card ───────────────────────────────────────────────── */}
      <Card title="Sync History">
        <Table
          columns={logColumns}
          dataSource={logs as HelmSyncLog[]}
          rowKey="id"
          size="small"
          pagination={false}
          locale={{ emptyText: 'No sync history yet' }}
        />
      </Card>
    </Flex>
  );
}
