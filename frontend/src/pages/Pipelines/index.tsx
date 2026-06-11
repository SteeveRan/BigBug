/**
 * @file index.tsx
 * @description Страница списка Pipeline Runs: таблица с columns/dataSource, модальное окно запуска, пагинация
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useState } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Modal,
  Input,
  Select,
  App,
  Tooltip,
  Segmented,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlayCircleOutlined,
  LinkOutlined,
  StopOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  useGetPipelineRunsQuery,
  useTriggerPipelineMutation,
  useCancelPipelineMutation,
  useRetryPipelineMutation,
  useGetGitlabInstancesQuery,
} from '../../store/api';
import { PipelineRun, STATUS_FLAG, GitlabInstance } from '../../types';
import { StatusChip } from '../../components/StatusChip';

// Sentinels for Segmented filter values — react requires non-undefined keys.
// -1 means "no filter" (All).
const STATUS_FILTER_ALL = -1;

const STATUS_FILTERS: { label: string; value: number }[] = [
  { label: 'All', value: STATUS_FILTER_ALL },
  { label: 'Running', value: STATUS_FLAG.IN_PROGRESS },
  { label: 'Success', value: STATUS_FLAG.OK },
  { label: 'Failed', value: STATUS_FLAG.FAILED },
];

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '-';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString();
}

export function PipelinesPage() {
  const { message } = App.useApp();
  const [statusFilter, setStatusFilter] = useState<number>(STATUS_FILTER_ALL);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({
    gitlab_instance_id: 0,
    gitlab_project_id: '',
    ref: '',
    variables: '',
  });

  const { data, isLoading } = useGetPipelineRunsQuery(
    { page, status: statusFilter === STATUS_FILTER_ALL ? undefined : statusFilter },
    { pollingInterval: statusFilter === STATUS_FLAG.IN_PROGRESS ? 5000 : 0 },
  );
  const [triggerPipeline, { isLoading: isTriggering }] = useTriggerPipelineMutation();
  const [cancelPipeline] = useCancelPipelineMutation();
  const [retryPipeline] = useRetryPipelineMutation();
  const { data: instances = [] } = useGetGitlabInstancesQuery();

  const handleTrigger = async () => {
    const variables: Record<string, string> = {};
    if (form.variables.trim()) {
      form.variables.split('\n').forEach((line) => {
        const [key, ...rest] = line.split('=');
        if (key.trim()) {
          variables[key.trim()] = rest.join('=').trim();
        }
      });
    }

    try {
      await triggerPipeline({
        gitlab_instance_id: form.gitlab_instance_id,
        gitlab_project_id: parseInt(form.gitlab_project_id, 10),
        ref: form.ref,
        variables,
      }).unwrap();
      message.success('Pipeline triggered successfully');
      setDialogOpen(false);
      setForm({ gitlab_instance_id: 0, gitlab_project_id: '', ref: '', variables: '' });
    } catch {
      // error handled by RTK Query
    }
  };

  const columns: ColumnsType<PipelineRun> = [
    {
      title: '#ID',
      key: 'id',
      render: (_: unknown, record: PipelineRun) =>
        record.gitlab_pipeline_id ? `#${record.gitlab_pipeline_id}` : `PR#${record.id}`,
    },
    {
      title: 'Project',
      dataIndex: 'gitlab_project_id',
      key: 'gitlab_project_id',
    },
    {
      title: 'Ref',
      key: 'ref',
      render: (_: unknown, record: PipelineRun) => (
        <Typography.Text code>{record.ref}</Typography.Text>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: PipelineRun) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: unknown, record: PipelineRun) => formatDuration(record.duration),
    },
    {
      title: 'Created',
      key: 'created',
      render: (_: unknown, record: PipelineRun) => formatDate(record.created_at),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: PipelineRun) => (
        <Flex gap={4} justify="flex-end">
          {record.web_url && (
            <Tooltip title="Open in GitLab">
              <Button
                size="small"
                icon={<LinkOutlined />}
                href={record.web_url}
                target="_blank"
                rel="noopener noreferrer"
              />
            </Tooltip>
          )}
          {record.status_flag === STATUS_FLAG.IN_PROGRESS && (
            <Tooltip title="Cancel">
              <Button
                size="small"
                danger
                icon={<StopOutlined />}
                onClick={() => cancelPipeline(record.id)}
              />
            </Tooltip>
          )}
          {record.status_flag === STATUS_FLAG.FAILED && (
            <Tooltip title="Retry">
              <Button
                size="small"
                type="primary"
                icon={<ReloadOutlined />}
                onClick={() => retryPipeline(record.id)}
              />
            </Tooltip>
          )}
        </Flex>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Pipeline Runs
        </Typography.Title>
        <Flex gap={12} wrap="wrap">
          <Segmented
            size="small"
            options={STATUS_FILTERS.map((f) => ({
              label: f.label,
              value: f.value,
            }))}
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v as number);
              setPage(1);
            }}
          />
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={() => setDialogOpen(true)}
          >
            Run Pipeline
          </Button>
        </Flex>
      </Flex>

      {/* ── Table ───────────────────────────────────────────────────────────── */}
      <Card>
        <Table
          columns={columns}
          dataSource={data?.items as PipelineRun[]}
          rowKey="id"
          loading={isLoading}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: data?.total ?? 0,
            showSizeChanger: true,
            pageSizeOptions: ['5', '10', '20', '50'],
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          locale={{ emptyText: 'No pipeline runs found' }}
        />
      </Card>

      {/* ── Run Pipeline Modal ──────────────────────────────────────────────── */}
      <Modal
        title="Run Pipeline"
        open={dialogOpen}
        onOk={handleTrigger}
        onCancel={() => setDialogOpen(false)}
        confirmLoading={isTriggering}
        okText="Trigger"
        cancelText="Cancel"
        okButtonProps={{
          disabled:
            isTriggering || !form.gitlab_instance_id || !form.gitlab_project_id || !form.ref,
        }}
      >
        <Flex vertical gap={16}>
          <Select
            placeholder="GitLab Instance"
            value={form.gitlab_instance_id || undefined}
            onChange={(v) => setForm({ ...form, gitlab_instance_id: v })}
            options={instances.map((inst: GitlabInstance) => ({
              label: `${inst.name} (${inst.url})`,
              value: inst.id,
            }))}
            style={{ width: '100%' }}
          />
          <Input
            placeholder="GitLab Project ID"
            value={form.gitlab_project_id}
            onChange={(e) => setForm({ ...form, gitlab_project_id: e.target.value })}
          />
          <Input
            placeholder="Ref (branch, tag, commit SHA)"
            value={form.ref}
            onChange={(e) => setForm({ ...form, ref: e.target.value })}
          />
          <Input.TextArea
            placeholder={'Variables (key=value, one per line)\nDEPLOY_ENV=staging\nVERSION=1.0.0'}
            value={form.variables}
            onChange={(e) => setForm({ ...form, variables: e.target.value })}
            rows={3}
          />
        </Flex>
      </Modal>
    </Flex>
  );
}
