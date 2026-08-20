/**
 * @file Settings/Pipelines/index.tsx
 * @description Settings page for managing GitLab CI/CD Components — CRUD with form
 *              modal, content editor (push/pull) and preset selector.
 * @dependencies antd, @ant-design/icons, ../../store/api, ../../types, ../../components/PermissionGate
 * @relatedFiles ../../store/api.ts, ../../types/index.ts, ../../components/PermissionGate.tsx
 */

import { useState } from 'react';
import { App } from 'antd';
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
  Form,
  Space,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  CloudUploadOutlined,
  CloudDownloadOutlined,
} from '@ant-design/icons';
import {
  useGetComponentsQuery,
  useGetComponentPresetsQuery,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
  useGetProvidersQuery,
  useGetGitlabProjectsQuery,
  usePushComponentMutation,
  usePullComponentMutation,
  useRunComponentMutation,
} from '../../../store/api';
import {
  GitLabComponent,
  GitLabComponentCreate,
  GitlabProject,
  ResourceProvider,
} from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';

const emptyForm: GitLabComponentCreate = {
  name: '',
  description: '',
  provider_id: undefined,
  project_path: '',
  gitlab_project_id: undefined,
  component_path: '',
  version: '',
  inputs_schema: undefined,
};

export function GitLabComponentsPage() {
  const { message } = App.useApp();
  const { data: components = [], isLoading } = useGetComponentsQuery();
  const { data: presets = [] } = useGetComponentPresetsQuery();
  const { data: providers = [] } = useGetProvidersQuery({
    subtype: 'gitlab',
    category: 'system',
    direction: 'internal',
  });
  const { data: projects = [] } = useGetGitlabProjectsQuery({ project_type: 'components' });
  const [createComponent] = useCreateComponentMutation();
  const [updateComponent] = useUpdateComponentMutation();
  const [deleteComponent] = useDeleteComponentMutation();
  const [pushComponent] = usePushComponentMutation();
  const [pullComponent] = usePullComponentMutation();
  const [runComponent, { isLoading: isRunning }] = useRunComponentMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<GitLabComponentCreate>({ ...emptyForm });
  const [submitting, setSubmitting] = useState(false);

  // State for Run Component modal
  const [runModalOpen, setRunModalOpen] = useState(false);
  const [selectedComponent, setSelectedComponent] = useState<GitLabComponent | null>(null);
  const [runForm] = Form.useForm();

  // State for Push/Pull content editor
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorComponent, setEditorComponent] = useState<GitLabComponent | null>(null);
  const [editorContent, setEditorContent] = useState('');
  const [editorPath, setEditorPath] = useState('');
  const [tagName, setTagName] = useState('');
  const [editorSaving, setEditorSaving] = useState(false);

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
      provider_id: component.provider_id,
      project_path: component.project_path,
      gitlab_project_id: component.gitlab_project_id ?? undefined,
      component_path: component.component_path,
      version: component.version ?? '',
      inputs_schema: component.inputs_schema ?? undefined,
    });
    setDialogOpen(true);
  };

  const handlePresetSelect = (key: string) => {
    const preset = presets.find((p) => p.key === key);
    if (!preset) return;
    const fileName = `${key.replace(/_/g, '-')}.yml`;
    setForm({
      ...form,
      name: form.name || preset.name,
      description: form.description || preset.description,
      component_path: `templates/${fileName}`,
      inputs_schema: preset.inputs_schema,
    });
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
      message.success(editingId ? 'Component updated' : 'Component created');
    } catch {
      message.error('Failed to save component');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Delete this component?')) {
      await deleteComponent(id);
    }
  };

  const openRunModal = (component: GitLabComponent) => {
    setSelectedComponent(component);
    runForm.setFieldsValue({
      ref: 'main',
      inputs: {},
    });
    setRunModalOpen(true);
  };

  const handleRunSubmit = async () => {
    if (!selectedComponent) return;

    try {
      const values = await runForm.validateFields();

      await runComponent({
        componentId: selectedComponent.id,
        data: {
          ref: values.ref,
          inputs: values.inputs || {},
        },
      }).unwrap();

      setRunModalOpen(false);
      runForm.resetFields();
      setSelectedComponent(null);
      message.success('Component run triggered successfully');
    } catch (error) {
      console.error('Failed to run component:', error);
      message.error(
        'Failed to trigger component run: ' +
          (error as { data?: { detail?: string } })?.data?.detail || 'Unknown error'
      );
    }
  };

  const openEditor = (component: GitLabComponent) => {
    setEditorComponent(component);
    setEditorContent('');
    setEditorPath(`templates/${component.component_path}`);
    setTagName('');
    setEditorOpen(true);
  };

  const handlePull = async (component: GitLabComponent) => {
    try {
      const result = await pullComponent(component.id).unwrap();
      setEditorComponent(component);
      setEditorContent(result.content);
      setEditorPath(result.file_path);
      setEditorOpen(true);
    } catch {
      message.error('Failed to pull component content');
    }
  };

  const handlePush = async () => {
    if (!editorComponent) return;
    setEditorSaving(true);
    try {
      await pushComponent({
        id: editorComponent.id,
        data: {
          content: editorContent,
          file_path: editorPath || undefined,
          tag_name: tagName || undefined,
        },
      }).unwrap();
      message.success('Component content pushed');
      setEditorOpen(false);
      setEditorComponent(null);
    } catch {
      message.error('Failed to push component content');
    } finally {
      setEditorSaving(false);
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
        <Flex gap={4} justify="flex-end">
          <PermissionGate permission="pipelines:write">
            <Tooltip title="Run">
              <Button
                size="small"
                type="text"
                icon={<PlayCircleOutlined />}
                onClick={() => openRunModal(record)}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="components:push">
            <Tooltip title="Edit content (push/pull)">
              <Button
                size="small"
                type="text"
                icon={<CloudUploadOutlined />}
                onClick={() => openEditor(record)}
              />
            </Tooltip>
            <Tooltip title="Pull content">
              <Button
                size="small"
                type="text"
                icon={<CloudDownloadOutlined />}
                onClick={() => handlePull(record)}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="components:write">
            <Tooltip title="Edit">
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => openEdit(record)}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="components:delete">
            <Tooltip title="Delete">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(record.id)}
              />
            </Tooltip>
          </PermissionGate>
        </Flex>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center">
        <Typography.Title level={5} style={{ margin: 0 }}>
          GitLab Components
        </Typography.Title>
        <PermissionGate permission="components:write">
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
            disabled={submitting || !form.name || !form.component_path}
          >
            {editingId ? 'Update' : 'Create'}
          </Button>,
        ]}
      >
        <Flex vertical gap={16}>
          <Select
            placeholder="Create from preset (optional)"
            allowClear
            onChange={handlePresetSelect}
            options={presets.map((p) => ({ label: p.name, value: p.key }))}
            style={{ width: '100%' }}
          />
          <Input
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input.TextArea
            placeholder="Description"
            value={form.description ?? ''}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
          />
          <Select
            placeholder="GitLab Project (components)"
            allowClear
            value={form.gitlab_project_id}
            onChange={(v) => setForm({ ...form, gitlab_project_id: v })}
            options={(projects as GitlabProject[]).map((p) => ({
              label: p.full_path,
              value: p.id,
            }))}
            style={{ width: '100%' }}
          />
          <Select
            placeholder="GitLab Provider (legacy)"
            value={form.provider_id || undefined}
            onChange={(v) => setForm({ ...form, provider_id: v })}
            options={providers.map((p: ResourceProvider) => ({
              label: p.label,
              value: p.id,
            }))}
            style={{ width: '100%' }}
          />
          <Input
            placeholder="my-group/my-project (legacy)"
            value={form.project_path ?? ''}
            onChange={(e) => setForm({ ...form, project_path: e.target.value })}
          />
          <Input
            placeholder="templates/my-component.yml"
            value={form.component_path}
            onChange={(e) => setForm({ ...form, component_path: e.target.value })}
          />
          <Input
            placeholder="1.0.0"
            value={form.version ?? ''}
            onChange={(e) => setForm({ ...form, version: e.target.value })}
          />
        </Flex>
      </Modal>

      {/* Push/Pull Content Editor Modal */}
      <Modal
        title={`Component Content: ${editorComponent?.name || ''}`}
        open={editorOpen}
        onCancel={() => setEditorOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setEditorOpen(false)}>
            Cancel
          </Button>,
          <Button key="push" type="primary" loading={editorSaving} onClick={handlePush}>
            Push
          </Button>,
        ]}
        width={720}
      >
        <Flex vertical gap={12}>
          <Input
            placeholder="file path"
            value={editorPath}
            onChange={(e) => setEditorPath(e.target.value)}
          />
          <Input.TextArea
            placeholder="component YAML content"
            value={editorContent}
            onChange={(e) => setEditorContent(e.target.value)}
            rows={16}
            style={{ fontFamily: 'monospace' }}
          />
          <Input
            placeholder="tag name (optional, e.g. v1.0.0)"
            value={tagName}
            onChange={(e) => setTagName(e.target.value)}
          />
        </Flex>
      </Modal>

      {/* Run Component Modal */}
      <Modal
        title={`Run Component: ${selectedComponent?.name || ''}`}
        open={runModalOpen}
        onCancel={() => setRunModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setRunModalOpen(false)}>
            Cancel
          </Button>,
          <Button key="run" type="primary" loading={isRunning} onClick={handleRunSubmit}>
            Run
          </Button>,
        ]}
      >
        <Form
          form={runForm}
          layout="vertical"
          initialValues={{
            ref: 'main',
            inputs: {},
          }}
        >
          <Form.Item
            label="GitLab Branch/Ref"
            name="ref"
            rules={[{ required: true, message: 'Please select a branch/ref' }]}
          >
            <Select
              placeholder="Select branch or tag"
              options={[
                { label: 'main', value: 'main' },
                { label: 'develop', value: 'develop' },
                { label: 'master', value: 'master' },
              ]}
              style={{ width: '100%' }}
            ></Select>
          </Form.Item>

          {selectedComponent?.inputs_schema && (
            <Form.Item label="Component Inputs">
              <Space orientation="vertical" style={{ width: '100%' }}>
                {Object.entries(selectedComponent.inputs_schema).map(([key, schema]) => {
                  const inputSchema = schema as {
                    type?: string;
                    title?: string;
                    default?: unknown;
                    description?: string;
                    enum?: string[];
                    required?: boolean;
                  };

                  let inputElement;
                  if (inputSchema.type === 'boolean') {
                    inputElement = (
                      <Select
                        options={[
                          { label: 'True', value: 'true' },
                          { label: 'False', value: 'false' },
                        ]}
                        placeholder={`Select ${inputSchema.title || key}`}
                      />
                    );
                  } else if (inputSchema.enum) {
                    inputElement = (
                      <Select
                        options={inputSchema.enum.map((option: string) => ({
                          label: option,
                          value: option,
                        }))}
                        placeholder={`Select ${inputSchema.title || key}`}
                      />
                    );
                  } else {
                    inputElement = (
                      <Input
                        type={inputSchema.type === 'password' ? 'password' : 'text'}
                        placeholder={`Enter ${inputSchema.title || key}`}
                      />
                    );
                  }

                  return (
                    <Form.Item
                      key={key}
                      label={inputSchema.title || key}
                      name={['inputs', key]}
                      tooltip={inputSchema.description}
                      rules={
                        inputSchema.required
                          ? [{ required: true, message: `Please enter ${key}` }]
                          : []
                      }
                    >
                      {inputElement}
                    </Form.Item>
                  );
                })}
              </Space>
            </Form.Item>
          )}
        </Form>
      </Modal>
    </Flex>
  );
}
