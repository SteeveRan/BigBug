/**
 * @file Settings/Integrations/Github.tsx
 * @description GitHub integration panel and dialog for managing GitHub instance connections.
 * @dependencies antd, @ant-design/icons, ../../../components/StatusChip, ./common
 * @relatedFiles ./common.ts, ../../../store/api.ts, ../../../types/index.ts
 */

import { useState } from 'react';
import { Card, Typography, Button, Table, Flex, Spin, Modal, Input, Checkbox, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { StatusChip } from '../../../components/StatusChip';
import type {
  GithubInstance,
  GithubInstanceCreate,
  GithubInstanceUpdate,
  ConnectionTestResult,
  StatusFlag,
} from '../../../types';
import {
  useGetGithubInstancesQuery,
  useCreateGithubInstanceMutation,
  useUpdateGithubInstanceMutation,
  useDeleteGithubInstanceMutation,
  useTestGithubConnectionMutation,
} from '../../../store/api';
import { DialogState, EMPTY_DIALOG, FormErrors, PanelProps } from './common';

// ═══════════════════════════════════════════════════════════════════════════════
// GitHub Panel
// ═══════════════════════════════════════════════════════════════════════════════

export function GithubPanel({ showMessage }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetGithubInstancesQuery();
  const [createInstance] = useCreateGithubInstanceMutation();
  const [updateInstance] = useUpdateGithubInstanceMutation();
  const [deleteInstance] = useDeleteGithubInstanceMutation();
  const [testConnection] = useTestGithubConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: GithubInstance) => {
    setDialog({
      open: true,
      mode: 'edit',
      instanceId: instance.id,
      defaultValues: {
        name: instance.name,
        token: '',
        is_active: instance.is_active,
        is_default: instance.is_default,
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete GitHub instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showMessage(`GitHub instance "${name}" deleted`, 'success');
    } catch {
      showMessage('Failed to delete GitHub instance', 'error');
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

  const columns: ColumnsType<GithubInstance> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Default',
      key: 'is_default',
      render: (_: unknown, record: GithubInstance) => (record.is_default ? 'Yes' : 'No'),
    },
    {
      title: 'Last Checked',
      key: 'last_checked',
      render: (_: unknown, record: GithubInstance) =>
        record.last_checked_at ? new Date(record.last_checked_at).toLocaleString() : 'Never',
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: GithubInstance) => (
        <StatusChip statusFlag={record.status_flag as StatusFlag} statusText={record.status_text} />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: GithubInstance) => (
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
          GitHub Instances
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          Add Instance
        </Button>
      </Flex>

      {isLoading && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin />
        </Flex>
      )}

      {isError && (
        <Typography.Text type="danger">
          Failed to load GitHub instances. Please try again later.
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
            locale={{ emptyText: 'No GitHub instances configured' }}
          />
        </Card>
      )}

      {dialog.open && (
        <GithubDialog
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

// ─── GitHub Dialog ────────────────────────────────────────────────────────────

interface GithubDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateGithubInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateGithubInstanceMutation>[0];
  showMessage: (message: string, severity: 'success' | 'error') => void;
}

function GithubDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showMessage,
}: GithubDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [token, setToken] = useState((dialogState.defaultValues?.token as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false
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

    if (!isEdit && !token.trim()) {
      newErrors.token = 'Token is required for new instances';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    console.log('handleSubmit called'); // Добавляем логирование
    if (!validate()) {
      console.log('Validation failed', errors); // Логируем ошибки валидации
      return;
    }

    setSubmitting(true);
    setApiError(null);

    try {
      const payload: GithubInstanceCreate | GithubInstanceUpdate = {
        name: name.trim(),
        token: token.trim() || null,
        is_active: isActive,
        is_default: isDefault,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as GithubInstanceUpdate,
        }).unwrap();
        showMessage('GitHub instance updated', 'success');
      } else {
        await createInstance(payload as GithubInstanceCreate).unwrap();
        showMessage('GitHub instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      console.error('Update GitLab instance error:', err); // Добавляем логирование ошибки
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
      title={isEdit ? 'Edit GitHub Instance' : 'Add GitHub Instance'}
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
          <Input.Password
            placeholder={isEdit ? 'Token (leave blank to keep current)' : 'Token'}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            status={errors.token ? 'error' : undefined}
            required={!isEdit}
          />
          {errors.token ? (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {errors.token}
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Personal Access Token (classic or fine-grained)
            </Typography.Text>
          )}
        </div>
        <Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)}>
          Active
        </Checkbox>
        <Checkbox checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)}>
          Default
        </Checkbox>
      </Flex>
    </Modal>
  );
}
