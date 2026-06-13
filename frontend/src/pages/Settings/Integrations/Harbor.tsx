/**
 * @file Settings/Integrations/Harbor.tsx
 * @description Harbor integration panel and dialog for managing Harbor registry connections.
 * @dependencies antd, @ant-design/icons, ../../../components/StatusChip, ./common
 * @relatedFiles ./common.ts, ../../../store/api.ts, ../../../types/index.ts
 */

import { useState } from 'react';
import { Card, Typography, Button, Table, Flex, Spin, Modal, Input, Checkbox, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { StatusChip } from '../../../components/StatusChip';
import type {
  HarborInstance,
  HarborInstanceCreate,
  HarborInstanceUpdate,
  ConnectionTestResult,
  StatusFlag,
} from '../../../types';
import {
  useGetHarborInstancesQuery,
  useCreateHarborInstanceMutation,
  useUpdateHarborInstanceMutation,
  useDeleteHarborInstanceMutation,
  useTestHarborConnectionMutation,
} from '../../../store/api';
import { DialogState, EMPTY_DIALOG, FormErrors, isValidUrl, PanelProps } from './common';

// ═══════════════════════════════════════════════════════════════════════════════
// Harbor Panel
// ═══════════════════════════════════════════════════════════════════════════════

export function HarborPanel({ showMessage }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetHarborInstancesQuery();
  const [createInstance] = useCreateHarborInstanceMutation();
  const [updateInstance] = useUpdateHarborInstanceMutation();
  const [deleteInstance] = useDeleteHarborInstanceMutation();
  const [testConnection] = useTestHarborConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: HarborInstance) => {
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
        default_project: instance.default_project ?? '',
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete Harbor instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showMessage(`Harbor instance "${name}" deleted`, 'success');
    } catch {
      showMessage('Failed to delete Harbor instance', 'error');
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

  const columns: ColumnsType<HarborInstance> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'URL', dataIndex: 'url', key: 'url' },
    { title: 'Username', dataIndex: 'username', key: 'username' },
    {
      title: 'Default',
      key: 'is_default',
      render: (_: unknown, record: HarborInstance) => (record.is_default ? 'Yes' : 'No'),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: HarborInstance) => (
        <StatusChip statusFlag={record.status_flag as StatusFlag} statusText={record.status_text} />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: HarborInstance) => (
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
          Internal Registries
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
          Failed to load Harbor instances. Please try again later.
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
            locale={{ emptyText: 'No Harbor instances configured' }}
          />
        </Card>
      )}

      {dialog.open && (
        <HarborDialog
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

// ─── Harbor Dialog ────────────────────────────────────────────────────────────

interface HarborDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateHarborInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateHarborInstanceMutation>[0];
  showMessage: (message: string, severity: 'success' | 'error') => void;
}

function HarborDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showMessage,
}: HarborDialogProps) {
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
  const [defaultProject, setDefaultProject] = useState(
    (dialogState.defaultValues?.default_project as string) ?? ''
  );
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
      const payload: HarborInstanceCreate | HarborInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        username: username.trim(),
        password: password.trim() || null,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
        default_project: defaultProject.trim() || null,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as HarborInstanceUpdate,
        }).unwrap();
        showMessage('Harbor instance updated', 'success');
      } else {
        await createInstance(payload as HarborInstanceCreate).unwrap();
        showMessage('Harbor instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      console.error('Update Harbor instance error:', err); // Добавляем логирование ошибки
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
      title={isEdit ? 'Edit Harbor Instance' : 'Add Harbor Instance'}
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
            placeholder="https://harbor.example.com"
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
              e.g. https://harbor.example.com
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
        <Input
          placeholder="Default Project"
          value={defaultProject}
          onChange={(e) => setDefaultProject(e.target.value)}
        />
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
