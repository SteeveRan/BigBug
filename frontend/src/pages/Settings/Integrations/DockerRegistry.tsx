/**
 * @file Settings/Integrations/DockerRegistry.tsx
 * @description Docker Registry integration panel and dialog for managing Docker registry connections.
 * @dependencies antd, @ant-design/icons, ../../../components/StatusChip, ./common
 * @relatedFiles ./common.ts, ../../../store/api.ts, ../../../types/index.ts
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
  InputNumber,
  Select,
  Checkbox,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { StatusChip } from '../../../components/StatusChip';
import type {
  DockerRegistryInstance,
  DockerRegistryInstanceCreate,
  DockerRegistryInstanceUpdate,
  ConnectionTestResult,
  StatusFlag,
} from '../../../types';
import {
  useGetDockerRegistryInstancesQuery,
  useCreateDockerRegistryInstanceMutation,
  useUpdateDockerRegistryInstanceMutation,
  useDeleteDockerRegistryInstanceMutation,
  useTestDockerRegistryConnectionMutation,
} from '../../../store/api';
import { DialogState, EMPTY_DIALOG, FormErrors, isValidUrl, PanelProps } from './common';

// ═══════════════════════════════════════════════════════════════════════════════
// Docker Registry Panel
// ═══════════════════════════════════════════════════════════════════════════════

export function DockerRegistryPanel({ showMessage }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetDockerRegistryInstancesQuery();
  const [createInstance] = useCreateDockerRegistryInstanceMutation();
  const [updateInstance] = useUpdateDockerRegistryInstanceMutation();
  const [deleteInstance] = useDeleteDockerRegistryInstanceMutation();
  const [testConnection] = useTestDockerRegistryConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: DockerRegistryInstance) => {
    setDialog({
      open: true,
      mode: 'edit',
      instanceId: instance.id,
      defaultValues: {
        name: instance.name,
        url: instance.url,
        username: instance.username,
        password: '',
        is_active: instance.is_active,
        verify_ssl: instance.verify_ssl,
        is_default: instance.is_default,
        registry_type: instance.registry_type,
        registry_provider: instance.registry_provider,
        priority: instance.priority,
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete Docker Registry instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showMessage(`Docker Registry instance "${name}" deleted`, 'success');
    } catch {
      showMessage('Failed to delete Docker Registry instance', 'error');
    }
  };

  const handleTest = async (id: number) => {
    setTestLoading(id);
    try {
      const result: ConnectionTestResult = await testConnection(id).unwrap();
      showMessage(
        result.success ? 'Connection successful' : `Connection failed: ${result.message}`,
        result.success ? 'success' : 'error'
      );
    } catch {
      showMessage('Connection test failed', 'error');
    } finally {
      setTestLoading(null);
    }
  };

  const columns: ColumnsType<DockerRegistryInstance> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'URL', dataIndex: 'url', key: 'url' },
    { title: 'Username', dataIndex: 'username', key: 'username' },
    {
      title: 'Default',
      key: 'is_default',
      render: (_: unknown, record: DockerRegistryInstance) => (record.is_default ? 'Yes' : 'No'),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: DockerRegistryInstance) => (
        <StatusChip statusFlag={record.status_flag as StatusFlag} statusText={record.status_text} />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: DockerRegistryInstance) => (
        <Flex gap={4} justify="flex-end">
          <Tooltip title="Edit">
            <Button
              size="small"
              type="text"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
              aria-label={`Edit ${record.name}`}
            />
          </Tooltip>
          <Tooltip title="Delete">
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDelete(record.id, record.name)}
              aria-label={`Delete ${record.name}`}
            />
          </Tooltip>
          <Tooltip title="Test Connection">
            <Button
              size="small"
              type="text"
              icon={<PlayCircleOutlined />}
              loading={testLoading === record.id}
              onClick={() => handleTest(record.id)}
              aria-label={`Test connection to ${record.name}`}
            />
          </Tooltip>
        </Flex>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center">
        <Typography.Title level={5} style={{ margin: 0 }}>
          External Registries
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          Add Registry
        </Button>
      </Flex>

      {isLoading && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin />
        </Flex>
      )}

      {isError && (
        <Typography.Text type="danger">
          Failed to load Docker Registry instances. Please try again later.
        </Typography.Text>
      )}

      {instances && (
        <Card>
          <Table
            columns={columns}
            dataSource={instances}
            rowKey="id"
            pagination={false}
            size="small"
            locale={{ emptyText: 'No Docker Registry instances configured' }}
          />
        </Card>
      )}

      {dialog.open && (
        <DockerRegistryDialog
          open={dialog}
          onClose={handleClose}
          createInstance={createInstance}
          updateInstance={updateInstance}
          showMessage={showMessage}
        />
      )}
    </Flex>
  );
}

// ─── Docker Registry Dialog ────────────────────────────────────────────────────

interface DockerRegistryDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateDockerRegistryInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateDockerRegistryInstanceMutation>[0];
  showMessage: (message: string, severity: 'success' | 'error') => void;
}

function DockerRegistryDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showMessage,
}: DockerRegistryDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [url, setUrl] = useState((dialogState.defaultValues?.url as string) ?? '');
  const [username, setUsername] = useState((dialogState.defaultValues?.username as string) ?? '');
  const [password, setPassword] = useState((dialogState.defaultValues?.password as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false
  );
  const [registryType, setRegistryType] = useState(
    (dialogState.defaultValues?.registry_type as string) ?? 'external'
  );
  const [registryProvider, setRegistryProvider] = useState(
    (dialogState.defaultValues?.registry_provider as string) ?? 'generic'
  );
  const [priority, setPriority] = useState((dialogState.defaultValues?.priority as number) ?? 0);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const isEdit = dialogState.mode === 'edit';

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!url.trim()) {
      newErrors.url = 'URL is required';
    } else if (!isValidUrl(url.trim())) {
      newErrors.url = 'Invalid URL format (must start with http:// or https://)';
    }

    if (!username.trim()) {
      newErrors.username = 'Username is required';
    }

    if (!isEdit && !password.trim()) {
      newErrors.password = 'Password is required for new instances';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    setApiError(null);

    try {
      const payload: DockerRegistryInstanceCreate | DockerRegistryInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        username: username.trim(),
        password: password.trim() || null,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
        registry_type: registryType,
        registry_provider: registryProvider,
        priority,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as DockerRegistryInstanceUpdate,
        }).unwrap();
        showMessage('Docker Registry instance updated', 'success');
      } else {
        await createInstance(payload as DockerRegistryInstanceCreate).unwrap();
        showMessage('Docker Registry instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Operation failed')
          : 'Operation failed';
      setApiError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={isEdit ? 'Edit Docker Registry Instance' : 'Add Docker Registry Instance'}
      open={dialogState.open}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>,
        <Button
          key="submit"
          type="primary"
          loading={submitting}
          onClick={handleSubmit}
          disabled={submitting}
        >
          {isEdit ? 'Update' : 'Create'}
        </Button>,
      ]}
    >
      <Flex vertical gap={16}>
        {apiError && <Typography.Text type="danger">{apiError}</Typography.Text>}
        <div>
          <Input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            status={errors.name ? 'error' : undefined}
            required
            autoFocus
          />
          {errors.name && (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {errors.name}
            </Typography.Text>
          )}
        </div>
        <div>
          <Input
            placeholder="https://registry.example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            status={errors.url ? 'error' : undefined}
            required
          />
          {errors.url ? (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {errors.url}
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              e.g. https://registry.example.com
            </Typography.Text>
          )}
        </div>
        <div>
          <Input
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            status={errors.username ? 'error' : undefined}
            required
          />
          {errors.username && (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {errors.username}
            </Typography.Text>
          )}
        </div>
        <div>
          <Input.Password
            placeholder={isEdit ? 'Password (leave blank to keep current)' : 'Password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            status={errors.password ? 'error' : undefined}
            required={!isEdit}
          />
          {errors.password && (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {errors.password}
            </Typography.Text>
          )}
        </div>
        <div>
          <Typography.Text
            type="secondary"
            style={{ fontSize: 12, display: 'block', marginBottom: 4 }}
          >
            Registry Type
          </Typography.Text>
          <Select
            value={registryType}
            onChange={(value) => {
              setRegistryType(value);
              if (value === 'internal') {
                setRegistryProvider('generic');
              }
            }}
            options={[
              { value: 'internal', label: 'Internal' },
              { value: 'external', label: 'External' },
            ]}
            style={{ width: '100%' }}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Whether this is an internal private registry or an external public registry
          </Typography.Text>
        </div>
        {registryType !== 'internal' && (
          <div>
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: 'block', marginBottom: 4 }}
            >
              Registry Provider
            </Typography.Text>
            <Select
              value={registryProvider}
              onChange={(value) => setRegistryProvider(value)}
              options={[
                { value: 'docker_hub', label: 'Docker Hub' },
                { value: 'quay_io', label: 'Quay.io' },
                { value: 'gcr', label: 'Google Container Registry' },
                { value: 'ecr', label: 'AWS ECR' },
                { value: 'acr', label: 'Azure Container Registry' },
                { value: 'ghcr', label: 'GitHub Container Registry' },
                { value: 'harbor', label: 'Harbor' },
                { value: 'generic', label: 'Generic' },
              ]}
              style={{ width: '100%' }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Auto-detected when adding images; used for matching
            </Typography.Text>
          </div>
        )}
        <div>
          <Typography.Text
            type="secondary"
            style={{ fontSize: 12, display: 'block', marginBottom: 4 }}
          >
            Priority
          </Typography.Text>
          <InputNumber
            min={0}
            max={100}
            value={priority}
            onChange={(value) => setPriority(value || 0)}
            style={{ width: '100%' }}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Higher values take precedence when multiple registries match
          </Typography.Text>
        </div>
        <Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)}>
          Active
        </Checkbox>
        <Checkbox checked={verifySsl} onChange={(e) => setVerifySsl(e.target.checked)}>
          Verify SSL
        </Checkbox>
        <Checkbox checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)}>
          Default
        </Checkbox>
      </Flex>
    </Modal>
  );
}
