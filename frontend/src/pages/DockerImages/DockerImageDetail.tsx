/**
 * @file DockerImageDetail.tsx
 * @description Страница деталей Docker Image: source info, sync schedule, теги, история синхронизации + модальное окно Index Image
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
  Modal,
  Input,
  App,
  Tooltip,
  Space,
  Switch,
  Badge,
  Popconfirm,
  Form,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  LinkOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useState } from 'react';
import {
  useGetDockerImageQuery,
  useGetDockerImageTagsQuery,
  useGetDockerImageLogsQuery,
  useIndexDockerImageMutation,
  useUpdateDockerImageMutation,
  useGetDockerSyncSchedulesQuery,
  useCreateDockerSyncScheduleMutation,
  useUpdateDockerSyncScheduleMutation,
  useDeleteDockerSyncScheduleMutation,
  useBatchDeleteDockerTagsMutation,
} from '../../store/api';
import {
  DockerImageSourceDetail,
  DockerImageTag,
  DockerSyncLog,
  DockerSyncSchedule,
} from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function DockerImageDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const sourceId = Number(id);

  const { data: source, isLoading } = useGetDockerImageQuery(sourceId);
  const { data: tags = [] } = useGetDockerImageTagsQuery(sourceId);
  const { data: logs = [] } = useGetDockerImageLogsQuery(sourceId);
  const { data: schedules = [] } = useGetDockerSyncSchedulesQuery(sourceId);
  const [indexImage, { isLoading: indexing }] = useIndexDockerImageMutation();

  // Batch tag deletion
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [batchDeleteDockerTags] = useBatchDeleteDockerTagsMutation();

  const [indexDialogOpen, setIndexDialogOpen] = useState(false);
  const [imageName, setImageName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [updateSource] = useUpdateDockerImageMutation();
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    target_registry_url: '',
    target_project: '',
  });

  // ── Schedule modal state ──────────────────────────────────────────────────
  const [createSchedule] = useCreateDockerSyncScheduleMutation();
  const [updateSchedule] = useUpdateDockerSyncScheduleMutation();
  const [deleteSchedule] = useDeleteDockerSyncScheduleMutation();
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<DockerSyncSchedule | null>(null);
  const [scheduleForm] = Form.useForm();

  const handleOpenEditDialog = () => {
    setEditForm({
      target_registry_url: s?.target_registry_url ?? '',
      target_project: s?.target_project ?? '',
    });
    setEditDialogOpen(true);
  };

  const handleEditSave = async () => {
    setSubmitting(true);
    try {
      await updateSource({
        id: sourceId,
        data: {
          target_registry_url: editForm.target_registry_url || null,
          target_project: editForm.target_project || null,
        },
      }).unwrap();
      message.success('Target registry settings updated');
      setEditDialogOpen(false);
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  const s = source as DockerImageSourceDetail | undefined;

  const handleIndex = async () => {
    setSubmitting(true);
    try {
      await indexImage({ id: sourceId, image_name: imageName }).unwrap();
      message.success(`Indexing started for ${imageName}`);
      setIndexDialogOpen(false);
      setImageName('');
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  // ── Schedule handlers ───────────────────────────────────────────────────
  const handleOpenAddSchedule = () => {
    setEditingSchedule(null);
    scheduleForm.resetFields();
    scheduleForm.setFieldsValue({
      cron_expression: '',
      is_enabled: true,
      use_default_schedule: true,
    });
    setScheduleModalOpen(true);
  };

  const handleOpenEditSchedule = (schedule: DockerSyncSchedule) => {
    setEditingSchedule(schedule);
    scheduleForm.setFieldsValue({
      cron_expression: schedule.cron_expression ?? '',
      is_enabled: schedule.is_enabled,
      use_default_schedule: schedule.use_default_schedule,
    });
    setScheduleModalOpen(true);
  };

  const handleScheduleSave = async () => {
    try {
      const values = await scheduleForm.validateFields();
      const data = {
        cron_expression: values.cron_expression || undefined,
        is_enabled: values.is_enabled,
        use_default_schedule: values.use_default_schedule,
      };

      if (editingSchedule) {
        await updateSchedule({
          sourceId,
          scheduleId: editingSchedule.id,
          data,
        }).unwrap();
        message.success('Schedule updated');
      } else {
        await createSchedule({ sourceId, data }).unwrap();
        message.success('Schedule created');
      }
      setScheduleModalOpen(false);
      scheduleForm.resetFields();
    } catch {
      // validation error or RTK Query error
    }
  };

  const handleDeleteSchedule = async (scheduleId: number) => {
    try {
      await deleteSchedule({ sourceId, scheduleId }).unwrap();
      message.success('Schedule deleted');
    } catch {
      // error handled by RTK Query
    }
  };

  const handleBatchDeleteTags = async () => {
    try {
      await batchDeleteDockerTags({ sourceId, tagIds: selectedTags }).unwrap();
      message.success(`Deleted ${selectedTags.length} tags`);
      setSelectedTags([]);
    } catch {
      message.error('Failed to delete tags');
    }
  };

  const formatBytes = (bytes: number | null): string => {
    if (bytes === null) return '—';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIdx = 0;
    while (size >= 1024 && unitIdx < units.length - 1) {
      size /= 1024;
      unitIdx++;
    }
    return `${size.toFixed(1)} ${units[unitIdx]}`;
  };

  const formatDate = (val: string | null): string => {
    if (!val) return '—';
    return new Date(val).toLocaleString();
  };

  // ── Loading / Not Found ──────────────────────────────────────────────────
  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: 48 }}>
        <Spin size="large" />
      </Flex>
    );
  }
  if (!s) {
    return (
      <Flex vertical align="center" gap={16} style={{ padding: 48 }}>
        <Typography.Text type="secondary">Docker image source not found</Typography.Text>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/docker-images')}>
          Back to Docker Images
        </Button>
      </Flex>
    );
  }

  // ── Schedule Table Columns ───────────────────────────────────────────────
  const scheduleColumns: ColumnsType<DockerSyncSchedule> = [
    {
      title: 'Cron Expression',
      dataIndex: 'cron_expression',
      key: 'cron_expression',
      render: (val: string | null, record: DockerSyncSchedule) => {
        if (record.use_default_schedule) {
          return (
            <Typography.Text type="secondary" italic>
              Using default schedule
            </Typography.Text>
          );
        }
        return val ? (
          <Typography.Text code>{val}</Typography.Text>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        );
      },
    },
    {
      title: 'Enabled',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      render: (val: boolean) =>
        val ? <Badge status="success" text="Yes" /> : <Badge status="default" text="No" />,
    },
    {
      title: 'Default Schedule',
      dataIndex: 'use_default_schedule',
      key: 'use_default_schedule',
      render: (val: boolean) =>
        val ? <Tag color="blue">Default</Tag> : <Tag color="orange">Custom</Tag>,
    },
    {
      title: 'Last Run',
      dataIndex: 'last_run_at',
      key: 'last_run_at',
      render: (val: string | null) => formatDate(val),
    },
    {
      title: 'Next Run',
      dataIndex: 'next_run_at',
      key: 'next_run_at',
      render: (val: string | null) => formatDate(val),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: DockerSyncSchedule) => (
        <Space size="small">
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleOpenEditSchedule(record)}
          >
            Edit
          </Button>
          <Popconfirm
            title="Delete schedule"
            description="Are you sure you want to delete this schedule?"
            onConfirm={() => handleDeleteSchedule(record.id)}
            okText="Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ── Tags Table Columns ───────────────────────────────────────────────────
  const tagColumns: ColumnsType<DockerImageTag> = [
    {
      title: 'Image',
      key: 'image',
      render: (_: unknown, record: DockerImageTag) => (
        <Typography.Text strong code style={{ fontSize: '0.8rem' }}>
          {record.image_name}
        </Typography.Text>
      ),
    },
    {
      title: 'Tag',
      dataIndex: 'tag',
      key: 'tag',
      render: (val: string) => (
        <Typography.Text code style={{ fontSize: '0.8rem' }}>
          {val}
        </Typography.Text>
      ),
    },
    {
      title: 'Architecture',
      dataIndex: 'architectures',
      key: 'architectures',
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
      title: 'Size',
      key: 'size',
      render: (_: unknown, record: DockerImageTag) => formatBytes(record.size_bytes),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: DockerImageTag) => (
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
  const logColumns: ColumnsType<DockerSyncLog> = [
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
      render: (_: unknown, record: DockerSyncLog) =>
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
      render: (_: unknown, record: DockerSyncLog) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: unknown, record: DockerSyncLog) => {
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
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/docker-images')}>
          Back
        </Button>
        <Typography.Title level={4} style={{ margin: 0, flex: 1 }}>
          {s.name}
        </Typography.Title>
        <Tooltip title={indexing ? 'Indexing…' : 'Index image tags from registry'}>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={() => setIndexDialogOpen(true)}
            loading={indexing}
          >
            Index Image
          </Button>
        </Tooltip>
        <Button
          icon={<LinkOutlined />}
          href={s.registry_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open Registry
        </Button>
      </Flex>

      {/* ── Info + Schedule + Tags Cards ────────────────────────────────────── */}
      <Flex gap={16} wrap="wrap">
        {/* Source Info Card */}
        <Card title="Source Info" style={{ flex: '1 1 300px', minWidth: 280 }}>
          <Flex vertical gap={12}>
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Status
              </Typography.Text>
              <StatusChip
                statusFlag={s.status_flag as 0 | 1 | 2 | 3 | 4}
                statusText={s.status_text}
              />
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Registry URL
              </Typography.Text>
              <Typography.Text code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                {s.registry_url}
              </Typography.Text>
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Description
              </Typography.Text>
              <Typography.Text>{s.description ?? '—'}</Typography.Text>
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Last Synced
              </Typography.Text>
              <Typography.Text>
                {s.last_synced_at
                  ? new Date(s.last_synced_at).toLocaleString()
                  : 'Never'}
              </Typography.Text>
            </Flex>
            {s.target_registry_url && (
              <>
                <Divider style={{ margin: 0 }} />
                <Flex vertical>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    Target Registry URL
                  </Typography.Text>
                  <Typography.Text code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                    {s.target_registry_url}
                  </Typography.Text>
                </Flex>
              </>
            )}
            {s.target_project && (
              <>
                <Divider style={{ margin: 0 }} />
                <Flex vertical>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    Target Project
                  </Typography.Text>
                  <Typography.Text code style={{ fontSize: '0.8rem' }}>
                    {s.target_project}
                  </Typography.Text>
                </Flex>
              </>
            )}
            {s.gitlab_project_url && (
              <>
                <Divider style={{ margin: 0 }} />
                <Flex vertical>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    GitLab Project
                  </Typography.Text>
                  <Typography.Link href={s.gitlab_project_url} target="_blank" rel="noopener noreferrer">
                    {s.gitlab_project_id ?? s.gitlab_project_url}
                  </Typography.Link>
                </Flex>
              </>
            )}
            <Divider style={{ margin: 0 }} />
            <Button
              size="small"
              onClick={handleOpenEditDialog}
              style={{ alignSelf: 'flex-start' }}
            >
              Edit Target Registry
            </Button>
          </Flex>
        </Card>

        {/* Sync Schedule Card */}
        <Card
          title={`Sync Schedule (${schedules.length})`}
          style={{ flex: '2 1 500px', minWidth: 350 }}
          extra={
            <Button
              size="small"
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleOpenAddSchedule}
            >
              Add Schedule
            </Button>
          }
        >
          <Table
            columns={scheduleColumns}
            dataSource={schedules as DockerSyncSchedule[]}
            rowKey="id"
            size="small"
            pagination={false}
            scroll={{ y: 360 }}
            locale={{
              emptyText: 'No schedules configured. Click "Add Schedule" to create one.',
            }}
          />
        </Card>

        {/* Image Tags Card */}
        <Card
          title={`Image Tags (${(tags as DockerImageTag[]).length})`}
          style={{ flex: '2 1 500px', minWidth: 350 }}
          extra={
            <Popconfirm
              title="Delete tags?"
              description={`Delete ${selectedTags.length} tags? This action cannot be undone.`}
              onConfirm={handleBatchDeleteTags}
              okText="Delete"
              cancelText="Cancel"
              okButtonProps={{ danger: true }}
              disabled={selectedTags.length === 0}
            >
              <Button
                size="small"
                danger
                icon={<DeleteOutlined />}
                disabled={selectedTags.length === 0}
              >
                Delete Selected{selectedTags.length > 0 ? ` (${selectedTags.length})` : ''}
              </Button>
            </Popconfirm>
          }
        >
          <Table
            columns={tagColumns}
            dataSource={tags as DockerImageTag[]}
            rowKey="id"
            size="small"
            pagination={false}
            scroll={{ y: 360 }}
            rowSelection={{
              type: 'checkbox',
              onChange: (_selectedRowKeys, selectedRows) => {
                setSelectedTags((selectedRows as DockerImageTag[]).map((row) => row.id));
              },
            }}
            locale={{
              emptyText: 'No tags indexed yet. Click "Index Image" to fetch tags.',
            }}
          />
        </Card>
      </Flex>

      {/* ── Sync History Card ───────────────────────────────────────────────── */}
      <Card title="Sync History">
        <Table
          columns={logColumns}
          dataSource={logs as DockerSyncLog[]}
          rowKey="id"
          size="small"
          pagination={false}
          locale={{ emptyText: 'No sync history yet' }}
        />
      </Card>

      {/* ── Edit Target Registry Modal ──────────────────────────────────────── */}
      <Modal
        title="Edit Target Registry"
        open={editDialogOpen}
        onOk={handleEditSave}
        onCancel={() => setEditDialogOpen(false)}
        confirmLoading={submitting}
        okText="Save"
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="Target Registry URL (e.g. https://harbor.example.com)"
            value={editForm.target_registry_url}
            onChange={(e) =>
              setEditForm({ ...editForm, target_registry_url: e.target.value })
            }
          />
          <Input
            placeholder="Target Project (e.g. library)"
            value={editForm.target_project}
            onChange={(e) =>
              setEditForm({ ...editForm, target_project: e.target.value })
            }
          />
        </Space>
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Configure the target registry where images will be synced. Leave empty to unset.
        </Typography.Text>
      </Modal>

      {/* ── Schedule Add/Edit Modal ─────────────────────────────────────────── */}
      <Modal
        title={editingSchedule ? 'Edit Sync Schedule' : 'Add Sync Schedule'}
        open={scheduleModalOpen}
        onOk={handleScheduleSave}
        onCancel={() => {
          setScheduleModalOpen(false);
          scheduleForm.resetFields();
        }}
        okText={editingSchedule ? 'Update' : 'Create'}
        cancelText="Cancel"
      >
        <Form
          form={scheduleForm}
          layout="vertical"
          initialValues={{
            cron_expression: '',
            is_enabled: true,
            use_default_schedule: true,
          }}
        >
          <Form.Item
            name="cron_expression"
            label="Cron Expression"
            rules={[
              {
                pattern: /^(\*|((\*\/)?([1-5]?\d)))\s+(\*|((\*\/)?(1?\d|2[0-3])))\s+(\*|((\*\/)?([12]?\d|3[01])))\s+(\*|((\*\/)?(1?\d|[12]\d|3[01])))\s+(\*|((\*\/)?([1-9]|1[0-2])))$/,
                message: 'Please enter a valid cron expression (e.g. */30 * * * *)',
              },
            ]}
          >
            <Input placeholder="*/30 * * * *" />
          </Form.Item>
          <Form.Item
            name="use_default_schedule"
            label="Use Default Schedule"
            valuePropName="checked"
            help="If enabled, the default schedule configured in settings will be used and cron_expression is ignored."
          >
            <Switch />
          </Form.Item>
          <Form.Item name="is_enabled" label="Enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Index Image Modal ───────────────────────────────────────────────── */}
      <Modal
        title="Index Image Tags"
        open={indexDialogOpen}
        onOk={handleIndex}
        onCancel={() => setIndexDialogOpen(false)}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !imageName }}
        okText="Index"
        cancelText="Cancel"
      >
        <Input
          placeholder="Image Name (e.g. library/nginx)"
          value={imageName}
          onChange={(e) => setImageName(e.target.value)}
          required
        />
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Full image name to index (e.g., library/nginx, bitnami/postgresql)
        </Typography.Text>
      </Modal>
    </Flex>
  );
}
