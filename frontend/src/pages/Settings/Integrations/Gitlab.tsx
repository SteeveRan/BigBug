/**
 * @file Settings/Integrations/Gitlab.tsx
 * @description GitLab integration panel and dialog for managing GitLab instance connections.
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
  Checkbox,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { StatusChip } from '../../../components/StatusChip';
import type {
  GitlabInstance,
  GitlabInstanceCreate,
  GitlabInstanceUpdate,
  ConnectionTestResult,
  StatusFlag,
} from '../../../types';
import {
  useGetGitlabInstancesQuery,
  useCreateGitlabInstanceMutation,
  useUpdateGitlabInstanceMutation,
  useDeleteGitlabInstanceMutation,
  useTestGitlabConnectionMutation,
} from '../../../store/api';
import { DialogState, EMPTY_DIALOG, FormErrors, isValidUrl, PanelProps } from './common';

// ═══════════════════════════════════════════════════════════════════════════════
// GitLab Panel
// ═══════════════════════════════════════════════════════════════════════════════

export function GitlabPanel({ showMessage }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetGitlabInstancesQuery();
  const [createInstance] = useCreateGitlabInstanceMutation();
  const [updateInstance] = useUpdateGitlabInstanceMutation();
  const [deleteInstance] = useDeleteGitlabInstanceMutation();
  const [testConnection] = useTestGitlabConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: GitlabInstance) => {
    setDialog({
      open: true,
      mode: 'edit',
      instanceId: instance.id,
      defaultValues: {
        name: instance.name,
        url: instance.url,
        token: '',
        is_active: instance.is_active,
        verify_ssl: instance.verify_ssl,
        is_default: instance.is_default,
        default_group_id: instance.default_group_id ?? '',
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete GitLab instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showMessage(`GitLab instance "${name}" deleted`, 'success');
    } catch {
      showMessage('Failed to delete GitLab instance', 'error');
    }
  };

  const handleTest = async (id: number) => {
    setTestLoading(id);
    try {
      const result: ConnectionTestResult = await testConnection(id).unwrap();
      showMessage(
        result.success ? 'Connection successful' : `Connection failed: ${result.message}`,
        result.success ? 'success' : 'error',
      );
    } catch {
      showMessage('Connection test failed', 'error');
    } finally {
      setTestLoading(null);
    }
  };

  const columns: ColumnsType<GitlabInstance> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'URL', dataIndex: 'url', key: 'url' },
    {
      title: 'Default',
      key: 'is_default',
      render: (_: unknown, record: GitlabInstance) => (record.is_default ? 'Yes' : 'No'),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: GitlabInstance) => (
        <StatusChip statusFlag={record.status_flag as StatusFlag} statusText={record.status_text} />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: GitlabInstance) => (
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
          GitLab Instances
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
          Failed to load GitLab instances. Please try again later.
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
            locale={{ emptyText: 'No GitLab instances configured' }}
          />
        </Card>
      )}

      {dialog.open && (
        <GitlabDialog
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

// ─── GitLab Dialog ────────────────────────────────────────────────────────────

interface GitlabDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateGitlabInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateGitlabInstanceMutation>[0];
  showMessage: (message: string, severity: 'success' | 'error') => void;
}

function GitlabDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showMessage,
}: GitlabDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [url, setUrl] = useState((dialogState.defaultValues?.url as string) ?? '');
  const [token, setToken] = useState((dialogState.defaultValues?.token as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true,
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true,
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false,
  );
  const [defaultGroupId, setDefaultGroupId] = useState(
    (dialogState.defaultValues?.default_group_id as string) ?? '',
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

    if (!isEdit && !token.trim()) {
      newErrors.token = 'Token is required for new instances';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    setApiError(null);

    try {
      let payload: GitlabInstanceCreate | GitlabInstanceUpdate;
      
      if (isEdit) {
        // При редактировании создаем объект с опциональными полями
        payload = {};
        
        // Добавляем поля только если они изменились
        if (name.trim()) {
          payload.name = name.trim();
        }
        if (url.trim()) {
          payload.url = url.trim();
        }
        
        // Всегда передаем изменяемые булевы поля
        payload.is_active = isActive;
        payload.verify_ssl = verifySsl;
        payload.is_default = isDefault;
        
        // Обработка default_group_id
        if (defaultGroupId && defaultGroupId.toString().trim() !== '') {
          const parsedGroupId = isNaN(Number(defaultGroupId)) ? null : Number(defaultGroupId);
          payload.default_group_id = parsedGroupId;
        } else {
          payload.default_group_id = null;
        }
        
        // Обработка токена: если поле не пустое, то обновляем токен, иначе не включаем в payload
        // Это позволяет не обновлять токен, если пользователь не ввел новое значение
        if (token !== '') {
          payload.token = token.trim() || null;
        }
      } else {
        // При создании передаем все поля
        payload = {
          name: name.trim(),
          url: url.trim(),
          token: token.trim() || null,
          is_active: isActive,
          verify_ssl: verifySsl,
          is_default: isDefault,
          default_group_id: defaultGroupId && defaultGroupId.toString().trim() !== '' ? (isNaN(Number(defaultGroupId)) ? null : Number(defaultGroupId)) : null,
        };
      }

      if (isEdit && dialogState.instanceId) {
        console.log('Calling updateInstance with:', { id: dialogState.instanceId, data: payload }); // Добавляем логирование
        const result = await updateInstance({
          id: dialogState.instanceId,
          data: payload as GitlabInstanceUpdate,
        });
        console.log('Update result:', result); // Логируем результат
        if ('error' in result) {
          console.error('Update error:', result.error); // Логируем ошибку
          throw result.error;
        }
        console.log('Update successful'); // Логируем успешное выполнение
        showMessage('GitLab instance updated', 'success');
      } else {
        console.log('Calling createInstance with:', payload); // Добавляем логирование
        const result = await createInstance(payload as GitlabInstanceCreate);
        console.log('Create result:', result); // Логируем результат
        if ('error' in result) {
          console.error('Create error:', result.error); // Логируем ошибку
          throw result.error;
        }
        console.log('Create successful'); // Логируем успешное выполнение
        showMessage('GitLab instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      console.error('Full error object:', err); // Дополнительное логирование ошибки
      const msg =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Operation failed')
          : 'Operation failed';
      setApiError(msg);
      console.error('Operation failed with error:', msg); // Логируем сообщение об ошибке
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={isEdit ? 'Edit GitLab Instance' : 'Add GitLab Instance'}
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
            placeholder="https://gitlab.example.com"
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
              e.g. https://gitlab.example.com
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
          {errors.token && (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {errors.token}
            </Typography.Text>
          )}
        </div>
        <div>
          <Input
            placeholder="Default Group ID"
            value={defaultGroupId}
            onChange={(e) => setDefaultGroupId(e.target.value)}
            type="number"
            status={errors.defaultGroupId ? 'error' : undefined}
          />
          {errors.defaultGroupId && (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {errors.defaultGroupId}
            </Typography.Text>
          )}
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
