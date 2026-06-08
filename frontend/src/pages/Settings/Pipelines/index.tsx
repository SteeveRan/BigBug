/**
 * @file Settings/Pipelines/index.tsx
 * @description Settings page for managing GitLab CI/CD Components — CRUD with form modal.
 * @dependencies antd, @ant-design/icons, ../../store/api, ../../types, ../../components/PermissionGate
 * @relatedFiles ../../store/api.ts, ../../types/index.ts, ../../components/PermissionGate.tsx
 */

import { useState } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Spin,
  Modal,
  Input,
  Select,
  Tag,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import {
  useGetComponentsQuery,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
  useGetGitlabInstancesQuery,
} from '../../../store/api';
import { GitLabComponent, GitLabComponentCreate, GitlabInstance } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';

const emptyForm: GitLabComponentCreate = {
  name: '',
  description: '',
  gitlab_instance_id: 0,
  project_path: '',
  component_path: '',
  version: '',
  inputs_schema: undefined,
};

export function GitLabComponentsPage() {
  const { data: components = [], isLoading } = useGetComponentsQuery();
  const { data: instances = [] } = useGetGitlabInstancesQuery();
  const [createComponent] = useCreateComponentMutation();
  const [updateComponent] = useUpdateComponentMutation();
  const [deleteComponent] = useDeleteComponentMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<GitLabComponentCreate>({ ...emptyForm });
  const [submitting, setSubmitting] = useState(false);

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...emptyForm });
    setDialogOpen(true);
  };

  const openEdit = (component: GitLabComponent) => {
    setEditingId(component.id);
    setForm({
      name: component.name,
      description: component.description ?? '',
      gitlab_instance_id: component.gitlab_instance_id,
      project_path: component.project_path,
      component_path: component.component_path,
      version: component.version ?? '',
      inputs_schema: component.inputs_schema ?? undefined,
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    setSubmitting(true);
    try {
      const payload: GitLabComponentCreate = {
        ...form,
        description: form.description || undefined,
        version: form.version || undefined,
      };

      if (editingId) {
        await updateComponent({ id: editingId, data: payload }).unwrap();
      } else {
        await createComponent(payload).unwrap();
      }
      setDialogOpen(false);
      setForm({ ...emptyForm });
      setEditingId(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Delete this component?')) {
      await deleteComponent(id);
    }
  };

  const columns: ColumnsType<GitLabComponent> = [
    {
      title: 'Name',
      key: 'name',
      render: (_: unknown, record: GitLabComponent) => (
        <Flex vertical gap={2}>
          <Typography.Text strong>{record.name}</Typography.Text>
          {record.description && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {record.description}
            </Typography.Text>
          )}
        </Flex>
      ),
    },
    {
      title: 'Project Path',
      dataIndex: 'project_path',
      key: 'project_path',
      render: (text: string) => (
        <Typography.Text code style={{ fontSize: 12 }}>
          {text}
        </Typography.Text>
      ),
    },
    {
      title: 'Component Path',
      dataIndex: 'component_path',
      key: 'component_path',
      render: (text: string) => (
        <Typography.Text code style={{ fontSize: 12 }}>
          {text}
        </Typography.Text>
      ),
    },
    {
      title: 'Version',
      dataIndex: 'version',
      key: 'version',
      render: (text: string | null) => text || '-',
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: GitLabComponent) => (
        <Tag color={record.is_enabled ? 'success' : 'default'}>
          {record.is_enabled ? 'Enabled' : 'Disabled'}
        </Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: GitLabComponent) => (
        <PermissionGate permission="pipelines:manage">
          <Flex gap={4} justify="flex-end">
            <Tooltip title="Edit">
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => openEdit(record)}
              />
            </Tooltip>
            <Tooltip title="Delete">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(record.id)}
              />
            </Tooltip>
          </Flex>
        </PermissionGate>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center">
        <Typography.Title level={5} style={{ margin: 0 }}>
          GitLab Components
        </Typography.Title>
        <PermissionGate permission="pipelines:manage">
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Add Component
          </Button>
        </PermissionGate>
      </Flex>

      {isLoading ? (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin />
        </Flex>
      ) : (
        <Card>
          <Table
            columns={columns}
            dataSource={components}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: 'No components registered' }}
          />
        </Card>
      )}

      {/* Add / Edit Modal */}
      <Modal
        title={editingId ? 'Edit Component' : 'Add Component'}
        open={dialogOpen}
        onCancel={() => setDialogOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setDialogOpen(false)}>
            Cancel
          </Button>,
          <Button
            key="save"
            type="primary"
            loading={submitting}
            onClick={handleSave}
            disabled={
              submitting ||
              !form.name ||
              !form.gitlab_instance_id ||
              !form.project_path ||
              !form.component_path
            }
          >
            {editingId ? 'Update' : 'Create'}
          </Button>,
        ]}
      >
        <Flex vertical gap={16}>
          <Input
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input.TextArea
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
          />
          <Select
            placeholder="GitLab Instance"
            value={form.gitlab_instance_id || undefined}
            onChange={(v) => setForm({ ...form, gitlab_instance_id: v })}
            options={instances.map((inst: GitlabInstance) => ({
              label: inst.name,
              value: inst.id,
            }))}
            style={{ width: '100%' }}
          />
          <Input
            placeholder="my-group/my-project"
            value={form.project_path}
            onChange={(e) => setForm({ ...form, project_path: e.target.value })}
          />
          <Input
            placeholder="templates/my-component.yml"
            value={form.component_path}
            onChange={(e) => setForm({ ...form, component_path: e.target.value })}
          />
          <Input
            placeholder="1.0.0"
            value={form.version}
            onChange={(e) => setForm({ ...form, version: e.target.value })}
          />
        </Flex>
      </Modal>
    </Flex>
  );
}
