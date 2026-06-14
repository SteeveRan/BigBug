/**
 * @file SyncGroups/index.tsx
 * @description Страница списка Sync Groups — таблица (Name, Description, Sync, Freshness, Actions).
 *              Детали (cron, concurrency, pipeline, mirrors) вынесены на SyncGroupDetail.
 * @dependencies antd, @ant-design/icons, RTK Query, react-router, PermissionGate
 */

import { useState } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Space,
  App,
  Tooltip,
  Spin,
  Alert,
  Empty,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  InputNumber,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router';
import {
  useGetSyncGroupsQuery,
  useCreateSyncGroupMutation,
  useUpdateSyncGroupMutation,
  useDeleteSyncGroupMutation,
  useApplyPipelineToGroupMutation,
  useGetPipelineConfigsQuery,
} from '../../../store/api';
import type { SyncGroup, SyncGroupCreate, SyncGroupUpdate } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';

interface SyncGroupFormValues {
  name: string;
  description?: string;
  pipeline_id?: number;
  sync_enabled: boolean;
  sync_cron?: string;
  sync_concurrency: number;
  freshness_enabled: boolean;
  freshness_cron?: string;
  freshness_concurrency: number;
}

const CRON_PATTERN =
  /^(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*\/\d+)\s+(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*\/\d+)\s+(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*\/\d+)\s+(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*\/\d+)\s+(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*\/\d+)$/;

const SyncGroupsPage = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm<SyncGroupFormValues>();
  const navigate = useNavigate();

  const { data: groups = [], isLoading, isError } = useGetSyncGroupsQuery();
  const { data: pipelines = [] } = useGetPipelineConfigsQuery();
  const [applyPipelineToGroup, { isLoading: isApplying }] = useApplyPipelineToGroupMutation();

  const [createSyncGroup, { isLoading: isCreating }] = useCreateSyncGroupMutation();
  const [updateSyncGroup, { isLoading: isUpdating }] = useUpdateSyncGroupMutation();
  const [deleteSyncGroup] = useDeleteSyncGroupMutation();

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editGroup, setEditGroup] = useState<SyncGroup | undefined>(undefined);
  const isEdit = !!editGroup;

  // Apply Pipeline modal state
  const [applyPipelineModalOpen, setApplyPipelineModalOpen] = useState(false);
  const [applyPipelineTarget, setApplyPipelineTarget] = useState<SyncGroup | undefined>(undefined);
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | undefined>(undefined);

  // Watch form switches for conditional rendering
  const syncEnabled = Form.useWatch('sync_enabled', form);
  const freshnessEnabled = Form.useWatch('freshness_enabled', form);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete sync group "${name}"?`)) return;
    try {
      await deleteSyncGroup(id).unwrap();
      message.success('Sync group deleted');
    } catch {
      message.error('Failed to delete sync group');
    }
  };

  const handleApplyPipeline = async () => {
    if (!applyPipelineTarget || !selectedPipelineId) return;
    try {
      await applyPipelineToGroup({
        id: applyPipelineTarget.id,
        pipeline_id: selectedPipelineId,
      }).unwrap();
      message.success(`Pipeline applied to "${applyPipelineTarget.name}"`);
      setApplyPipelineModalOpen(false);
      setApplyPipelineTarget(undefined);
      setSelectedPipelineId(undefined);
    } catch {
      message.error('Failed to apply pipeline');
    }
  };

  const handleSubmitModal = async (values: SyncGroupFormValues) => {
    try {
      const sync_cron = values.sync_enabled ? values.sync_cron || null : null;
      const sync_concurrency = values.sync_enabled ? values.sync_concurrency || 1 : 1;
      const freshness_cron = values.freshness_enabled ? values.freshness_cron || null : null;
      const freshness_concurrency = values.freshness_enabled
        ? values.freshness_concurrency || 1
        : 1;

      const commonData = {
        name: values.name,
        description: values.description,
        pipeline_id: values.pipeline_id,
        sync_enabled: values.sync_enabled,
        sync_cron,
        sync_concurrency,
        freshness_enabled: values.freshness_enabled,
        freshness_cron,
        freshness_concurrency,
      };

      if (isEdit && editGroup) {
        const data: SyncGroupUpdate = { ...commonData };
        await updateSyncGroup({ id: editGroup.id, data }).unwrap();
        message.success('Sync group updated');
      } else {
        const data: SyncGroupCreate = { ...commonData };
        await createSyncGroup(data).unwrap();
        message.success('Sync group created');
      }
      form.resetFields();
      setModalOpen(false);
      setEditGroup(undefined);
    } catch {
      // error handled by RTK Query
    }
  };

  const columns: ColumnsType<SyncGroup> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      render: (name: string, record: SyncGroup) => (
        <Space>
          <Typography.Link onClick={() => navigate(`/git-mirroring/sync-groups/${record.id}`)}>
            {name}
          </Typography.Link>
          {record.is_default && <Tag color="blue">Default</Tag>}
        </Space>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (desc: string | undefined) =>
        desc ? (
          <Typography.Text type="secondary">{desc}</Typography.Text>
        ) : (
          '—'
        ),
    },
    {
      title: 'Sync',
      dataIndex: 'sync_enabled',
      key: 'sync_enabled',
      width: 80,
      render: (enabled: boolean) => <Switch checked={enabled} disabled size="small" />,
    },
    {
      title: 'Freshness',
      dataIndex: 'freshness_enabled',
      key: 'freshness_enabled',
      width: 100,
      render: (enabled: boolean) => <Switch checked={enabled} disabled size="small" />,
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 160,
      render: (_: unknown, record: SyncGroup) => (
        <Space size={4}>
          <PermissionGate permission="sync_groups:write">
            <Tooltip title="Apply Pipeline">
              <Button
                size="small"
                type="text"
                icon={<ThunderboltOutlined />}
                onClick={() => {
                  setApplyPipelineTarget(record);
                  setSelectedPipelineId(undefined);
                  setApplyPipelineModalOpen(true);
                }}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="sync_groups:write">
            <Tooltip title="Edit">
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => {
                  setEditGroup(record);
                  setModalOpen(true);
                  form.setFieldsValue({
                    name: record.name,
                    description: record.description,
                    pipeline_id: record.pipeline_id ?? undefined,
                    sync_enabled: record.sync_enabled,
                    sync_cron: record.sync_cron || undefined,
                    sync_concurrency: record.sync_concurrency,
                    freshness_enabled: record.freshness_enabled,
                    freshness_cron: record.freshness_cron || undefined,
                    freshness_concurrency: record.freshness_concurrency,
                  });
                }}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="sync_groups:write">
            <Tooltip title="Delete">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(record.id, record.name)}
              />
            </Tooltip>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Sync Groups
        </Typography.Title>
        <PermissionGate permission="sync_groups:write">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditGroup(undefined);
              form.resetFields();
              setModalOpen(true);
            }}
          >
            Create Sync Group
          </Button>
        </PermissionGate>
      </Flex>

      {/* ── Content ─────────────────────────────────────────────────────────── */}
      {isLoading && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      )}

      {isError && (
        <Alert
          message="Failed to load sync groups"
          description="Please try again later."
          type="error"
          showIcon
        />
      )}

      {!isLoading && !isError && (
        <Card>
          <Table
            columns={columns}
            dataSource={groups as SyncGroup[]}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: <Empty description="No sync groups configured" /> }}
          />
        </Card>
      )}

      {/* ── Create/Edit Sync Group Modal ────────────────────────────────────── */}
      <Modal
        title={isEdit ? 'Edit Sync Group' : 'Create Sync Group'}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          setEditGroup(undefined);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={isCreating || isUpdating}
        okText={isEdit ? 'Update' : 'Create'}
        cancelText="Cancel"
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmitModal}
          initialValues={{
            sync_enabled: false,
            sync_concurrency: 1,
            freshness_enabled: false,
            freshness_concurrency: 1,
          }}
        >
          <Form.Item
            name="name"
            label="Name"
            rules={[{ required: true, message: 'Sync group name is required' }]}
          >
            <Input placeholder="e.g. Hourly Sync" />
          </Form.Item>

          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} placeholder="Optional description" />
          </Form.Item>

          <Form.Item name="pipeline_id" label="Pipeline">
            <Select
              placeholder="Select pipeline"
              allowClear
              options={pipelines?.map((p) => ({
                value: p.id,
                label: p.name,
              }))}
            />
          </Form.Item>

          {/* ── Sync Settings ─────────────────────────────────────────────── */}
          <Typography.Title level={5} style={{ marginBottom: 8 }}>
            Sync Settings
          </Typography.Title>

          <Form.Item name="sync_enabled" label="Sync Enabled" valuePropName="checked">
            <Switch />
          </Form.Item>

          {syncEnabled && (
            <Form.Item
              name="sync_cron"
              label="Sync Cron"
              rules={[
                {
                  pattern: CRON_PATTERN,
                  message: 'Invalid cron expression (5 fields required)',
                },
              ]}
            >
              <Input placeholder="0 */6 * * *" />
            </Form.Item>
          )}

          {syncEnabled && (
            <Form.Item name="sync_concurrency" label="Sync Concurrency">
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
          )}

          {/* ── Freshness Settings ─────────────────────────────────────────── */}
          <Typography.Title level={5} style={{ marginBottom: 8 }}>
            Freshness Settings
          </Typography.Title>

          <Form.Item name="freshness_enabled" label="Freshness Enabled" valuePropName="checked">
            <Switch />
          </Form.Item>

          {freshnessEnabled && (
            <Form.Item
              name="freshness_cron"
              label="Freshness Cron"
              rules={[
                {
                  pattern: CRON_PATTERN,
                  message: 'Invalid cron expression (5 fields required)',
                },
              ]}
            >
              <Input placeholder="0 0 * * *" />
            </Form.Item>
          )}

          {freshnessEnabled && (
            <Form.Item name="freshness_concurrency" label="Freshness Concurrency">
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* ── Apply Pipeline Modal ────────────────────────────────────────────── */}
      <Modal
        title={
          applyPipelineTarget ? `Apply Pipeline to "${applyPipelineTarget.name}"` : 'Apply Pipeline'
        }
        open={applyPipelineModalOpen}
        onOk={handleApplyPipeline}
        onCancel={() => {
          setApplyPipelineModalOpen(false);
          setApplyPipelineTarget(undefined);
          setSelectedPipelineId(undefined);
        }}
        confirmLoading={isApplying}
        okText="Apply"
        cancelText="Cancel"
        okButtonProps={{ disabled: !selectedPipelineId }}
        destroyOnHidden
      >
        <Form.Item label="Pipeline Configuration">
          <Select
            placeholder="Select a pipeline configuration"
            options={pipelines?.map((p) => ({
              value: p.id,
              label: p.name,
            }))}
            value={selectedPipelineId}
            onChange={setSelectedPipelineId}
            style={{ width: '100%' }}
          />
        </Form.Item>
      </Modal>
    </Flex>
  );
};

export default SyncGroupsPage;
