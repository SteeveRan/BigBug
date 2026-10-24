/**
 * @file HelmChartDetail.tsx
 * @description Страница деталей Helm Chart: source info, версии, история синхронизации + модальное окно синхронизации
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useParams, useNavigate } from 'react-router';
import { useState } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Spin,
  Divider,
  Modal,
  Input,
  App,
  Tooltip,
  Select,
  Alert,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  LinkOutlined,
  EditOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons';
import {
  useGetHelmChartQuery,
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
  useIndexHelmChartMutation,
  useSyncHelmChartMutation,
  useUpdateHelmChartMutation,
} from '../../store/api';
import { HelmChartSourceDetail, HelmChartVersion, HelmSyncLog } from '../../types';
import { StatusChip } from '../../components/StatusChip';
import { PermissionGate } from '../../components/PermissionGate';

export function HelmChartDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const chartId = Number(id);

  const { data: chart, isLoading } = useGetHelmChartQuery(chartId);
  const { data: versions = [] } = useGetHelmChartVersionsQuery(chartId);
  const { data: logs = [] } = useGetHelmChartLogsQuery(chartId);
  const [indexChart, { isLoading: indexing }] = useIndexHelmChartMutation();
  const [syncChart, { isLoading: syncing }] = useSyncHelmChartMutation();
  const [updateChart] = useUpdateHelmChartMutation();

  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [targetRepoUrl, setTargetRepoUrl] = useState('');
  const [gitlabProjectId, setGitlabProjectId] = useState('');
  const [savingTarget, setSavingTarget] = useState(false);

  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const [syncChartName, setSyncChartName] = useState<string | undefined>();
  const [syncVersion, setSyncVersion] = useState<string | undefined>();
  const [syncError, setSyncError] = useState<string | null>(null);

  const c = chart as HelmChartSourceDetail | undefined;
  const versionList = versions as HelmChartVersion[];

  // Unique chart names for the first sync selector.
  const chartNameOptions = Array.from(new Set(versionList.map((v) => v.chart_name))).map(
    (name) => ({ label: name, value: name })
  );
  const versionOptions = versionList
    .filter((v) => v.chart_name === syncChartName)
    .map((v) => ({ label: v.version, value: v.version }));

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

  const handleOpenEdit = () => {
    setTargetRepoUrl(c.target_repo_url ?? '');
    setGitlabProjectId(c.gitlab_project_id ?? '');
    setEditDialogOpen(true);
  };

  const handleEditSave = async () => {
    setSavingTarget(true);
    try {
      await updateChart({
        id: chartId,
        data: {
          target_repo_url: targetRepoUrl || null,
          gitlab_project_id: gitlabProjectId || null,
        },
      }).unwrap();
      message.success('Target repository updated');
      setEditDialogOpen(false);
    } catch {
      // error handled by RTK Query
    } finally {
      setSavingTarget(false);
    }
  };

  const handleOpenSync = () => {
    setSyncError(null);
    const first = versionList[0];
    setSyncChartName(first?.chart_name);
    setSyncVersion(first?.version);
    setSyncDialogOpen(true);
  };

  const handleSync = async () => {
    if (!syncChartName || !syncVersion) return;
    setSyncError(null);
    try {
      const result = await syncChart({
        id: chartId,
        chart_name: syncChartName,
        version: syncVersion,
      }).unwrap();
      message.success('Синхронизация запущена');
      setSyncDialogOpen(false);
      if (result.status_flag === 1) {
        message.error('Синхронизация не удалась');
      }
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'data' in err
          ? (err as { data?: { detail?: string } }).data?.detail
          : undefined;
      setSyncError(detail || 'Не удалось запустить синхронизацию');
    }
  };

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
      title: 'Chart / Version',
      key: 'chart_version',
      render: (_: unknown, record: HelmSyncLog) =>
        record.chart_name ? (
          <Typography.Text code style={{ fontSize: '0.8rem' }}>
            {record.chart_name}:{record.chart_version}
          </Typography.Text>
        ) : (
          '—'
        ),
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
            (new Date(record.finished_at).getTime() - new Date(record.started_at).getTime()) / 1000
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
        <PermissionGate permission="helm:sync">
          <Tooltip
            title={
              c.gitlab_project_id
                ? 'Синхронизировать версию чарта в целевой репозиторий'
                : 'No GitLab project configured for syncing'
            }
          >
            <Button
              icon={<CloudUploadOutlined />}
              onClick={handleOpenSync}
              loading={syncing}
              disabled={!c.gitlab_project_id}
            >
              Синхронизировать
            </Button>
          </Tooltip>
        </PermissionGate>
        <Button icon={<LinkOutlined />} href={c.repo_url} target="_blank" rel="noopener noreferrer">
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
              <Flex justify="space-between" align="center">
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Target Repository
                </Typography.Text>
                <PermissionGate permission="helm:write">
                  <Button size="small" type="link" icon={<EditOutlined />} onClick={handleOpenEdit}>
                    Edit
                  </Button>
                </PermissionGate>
              </Flex>
              <Typography.Text code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                {c.target_repo_url ?? 'Not configured'}
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
                {c.last_synced_at ? new Date(c.last_synced_at).toLocaleString() : 'Never'}
              </Typography.Text>
            </Flex>
            {c.gitlab_project_url && (
              <>
                <Divider style={{ margin: 0 }} />
                <Flex vertical>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    GitLab Project
                  </Typography.Text>
                  <Typography.Link
                    href={c.gitlab_project_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {c.gitlab_project_id ?? c.gitlab_project_url}
                  </Typography.Link>
                </Flex>
              </>
            )}
          </Flex>
        </Card>

        {/* Chart Versions Card */}
        <Card
          title={`Chart Versions (${versionList.length})`}
          style={{ flex: '2 1 500px', minWidth: 350 }}
        >
          <Table
            columns={versionColumns}
            dataSource={versionList}
            rowKey="id"
            size="small"
            pagination={false}
            scroll={{ y: 360 }}
            locale={{
              emptyText: 'No versions indexed yet. Click "Re-index" to fetch chart versions.',
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

      {/* ── Edit Target Modal ────────────────────────────────────────────────── */}
      <Modal
        title="Edit Target Repository"
        open={editDialogOpen}
        onOk={handleEditSave}
        onCancel={() => setEditDialogOpen(false)}
        confirmLoading={savingTarget}
        okText="Save"
        cancelText="Cancel"
      >
        <Flex vertical gap={8}>
          <Input
            placeholder="Target Helm repo URL (e.g. oci://harbor.local/bigbug)"
            value={targetRepoUrl}
            onChange={(e) => setTargetRepoUrl(e.target.value)}
          />
          <Input
            placeholder="GitLab Project ID (числовой, для sync-пайплайнов)"
            value={gitlabProjectId}
            onChange={(e) => setGitlabProjectId(e.target.value)}
          />
        </Flex>
      </Modal>

      {/* ── Sync Modal ──────────────────────────────────────────────────────── */}
      <Modal
        title="Синхронизация чарта"
        open={syncDialogOpen}
        onOk={handleSync}
        onCancel={() => setSyncDialogOpen(false)}
        confirmLoading={syncing}
        okButtonProps={{ disabled: !syncChartName || !syncVersion }}
        okText="Синхронизировать"
        cancelText="Cancel"
      >
        <Flex vertical gap={8}>
          <Select
            style={{ width: '100%' }}
            placeholder="Select chart"
            showSearch
            optionFilterProp="label"
            value={syncChartName}
            onChange={(val) => {
              setSyncChartName(val);
              setSyncVersion(undefined);
            }}
            options={chartNameOptions}
          />
          <Select
            style={{ width: '100%' }}
            placeholder="Select version"
            showSearch
            optionFilterProp="label"
            value={syncVersion}
            onChange={(val) => setSyncVersion(val)}
            options={versionOptions}
            disabled={!syncChartName}
          />
          {syncError && <Alert type="error" title={syncError} showIcon />}
        </Flex>
      </Modal>
    </Flex>
  );
}
