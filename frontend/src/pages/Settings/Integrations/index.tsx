/**
 * @file Settings/Integrations/index.tsx
 * @description Settings page for managing integration instances (GitLab, Harbor, GitHub, Docker Registry, Helm Repository).
 *              Uses Ant Design Tabs, Tables, Modals for CRUD operations and connection testing.
 * @dependencies antd, @ant-design/icons, ../../store/api, ../../components/StatusChip
 * @relatedFiles ../../store/api.ts, ../../types/index.ts, ../../components/PermissionGate.tsx
 */

import { useState, useCallback } from 'react';
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
  App,
  Tabs,
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
  HarborInstance,
  HarborInstanceCreate,
  HarborInstanceUpdate,
  GithubInstance,
  GithubInstanceCreate,
  GithubInstanceUpdate,
  DockerRegistryInstance,
  DockerRegistryInstanceCreate,
  DockerRegistryInstanceUpdate,
  HelmRepositoryInstance,
  HelmRepositoryInstanceCreate,
  HelmRepositoryInstanceUpdate,
  ConnectionTestResult,
  StatusFlag,
} from '../../../types';
import {
  useGetGitlabInstancesQuery,
  useCreateGitlabInstanceMutation,
  useUpdateGitlabInstanceMutation,
  useDeleteGitlabInstanceMutation,
  useTestGitlabConnectionMutation,
  useGetHarborInstancesQuery,
  useCreateHarborInstanceMutation,
  useUpdateHarborInstanceMutation,
  useDeleteHarborInstanceMutation,
  useTestHarborConnectionMutation,
  useGetGithubInstancesQuery,
  useCreateGithubInstanceMutation,
  useUpdateGithubInstanceMutation,
  useDeleteGithubInstanceMutation,
  useTestGithubConnectionMutation,
  useGetDockerRegistryInstancesQuery,
  useCreateDockerRegistryInstanceMutation,
  useUpdateDockerRegistryInstanceMutation,
  useDeleteDockerRegistryInstanceMutation,
  useTestDockerRegistryConnectionMutation,
  useGetHelmRepositoryInstancesQuery,
  useCreateHelmRepositoryInstanceMutation,
  useUpdateHelmRepositoryInstanceMutation,
  useDeleteHelmRepositoryInstanceMutation,
  useTestHelmRepositoryConnectionMutation,
} from '../../../store/api';

// ─── Constants ───────────────────────────────────────────────────────────────

const TAB_LABELS = ['GitLab', 'Harbor', 'GitHub', 'Docker Registry', 'Helm Repository'] as const;

// ─── Dialog state ────────────────────────────────────────────────────────────

interface DialogState {
  open: boolean;
  mode: 'add' | 'edit';
  instanceId?: number;
  defaultValues?: Record<string, unknown>;
}

const EMPTY_DIALOG: DialogState = { open: false, mode: 'add' };

// ─── Form validation helpers ─────────────────────────────────────────────────

function isValidUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

interface FormErrors {
  name?: string;
  url?: string;
  username?: string;
  token?: string;
  password?: string;
}

// ─── Panel props ─────────────────────────────────────────────────────────────

interface PanelProps {
  showMessage: (message: string, severity: 'success' | 'error') => void;
}

// ─── Main component ──────────────────────────────────────────────────────────

export function SettingsIntegrations() {
  const { message } = App.useApp();
  const [tabIndex, setTabIndex] = useState(0);

  const showMessage = useCallback(
    (msg: string, severity: 'success' | 'error') => {
      if (severity === 'success') {
        message.success(msg);
      } else {
        message.error(msg);
      }
    },
    [message],
  );

  return (
    <Flex vertical gap={16}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        Settings
      </Typography.Title>

      <Tabs
        activeKey={String(tabIndex)}
        onChange={(key) => setTabIndex(Number(key))}
        items={TAB_LABELS.map((label, i) => ({
          key: String(i),
          label,
          children:
            i === 0 ? (
              <GitlabPanel showMessage={showMessage} />
            ) : i === 1 ? (
              <HarborPanel showMessage={showMessage} />
            ) : i === 2 ? (
              <GithubPanel showMessage={showMessage} />
            ) : i === 3 ? (
              <DockerRegistryPanel showMessage={showMessage} />
            ) : (
              <HelmRepositoryPanel showMessage={showMessage} />
            ),
        }))}
      />
    </Flex>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// GitLab Panel
// ═══════════════════════════════════════════════════════════════════════════════

function GitlabPanel({ showMessage }: PanelProps) {
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
      const payload: GitlabInstanceCreate | GitlabInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        token: token.trim() || undefined,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
        default_group_id: defaultGroupId.trim() ? Number(defaultGroupId) : null,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as GitlabInstanceUpdate,
        }).unwrap();
        showMessage('GitLab instance updated', 'success');
      } else {
        await createInstance(payload as GitlabInstanceCreate).unwrap();
        showMessage('GitLab instance created', 'success');
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
        <Input
          placeholder="Default Group ID"
          value={defaultGroupId}
          onChange={(e) => setDefaultGroupId(e.target.value)}
          type="number"
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

// ═══════════════════════════════════════════════════════════════════════════════
// Harbor Panel
// ═══════════════════════════════════════════════════════════════════════════════

function HarborPanel({ showMessage }: PanelProps) {
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
        result.success ? 'success' : 'error',
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
          Harbor Instances
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
    (dialogState.defaultValues?.is_active as boolean) ?? true,
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true,
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false,
  );
  const [defaultProject, setDefaultProject] = useState(
    (dialogState.defaultValues?.default_project as string) ?? '',
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
        password: password.trim() || undefined,
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

// ═══════════════════════════════════════════════════════════════════════════════
// GitHub Panel
// ═══════════════════════════════════════════════════════════════════════════════

function GithubPanel({ showMessage }: PanelProps) {
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
        result.success ? 'success' : 'error',
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
    (dialogState.defaultValues?.is_active as boolean) ?? true,
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false,
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
    if (!validate()) return;

    setSubmitting(true);
    setApiError(null);

    try {
      const payload: GithubInstanceCreate | GithubInstanceUpdate = {
        name: name.trim(),
        token: token.trim() || undefined,
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

// ═══════════════════════════════════════════════════════════════════════════════
// Docker Registry Panel
// ═══════════════════════════════════════════════════════════════════════════════

function DockerRegistryPanel({ showMessage }: PanelProps) {
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
        result.success ? 'success' : 'error',
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
      render: (_: unknown, record: DockerRegistryInstance) =>
        record.is_default ? 'Yes' : 'No',
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
          Docker Registry Instances
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
    (dialogState.defaultValues?.is_active as boolean) ?? true,
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true,
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false,
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
      const payload: DockerRegistryInstanceCreate | DockerRegistryInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        username: username.trim(),
        password: password.trim() || undefined,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
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

// ═══════════════════════════════════════════════════════════════════════════════
// Helm Repository Panel
// ═══════════════════════════════════════════════════════════════════════════════

function HelmRepositoryPanel({ showMessage }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetHelmRepositoryInstancesQuery();
  const [createInstance] = useCreateHelmRepositoryInstanceMutation();
  const [updateInstance] = useUpdateHelmRepositoryInstanceMutation();
  const [deleteInstance] = useDeleteHelmRepositoryInstanceMutation();
  const [testConnection] = useTestHelmRepositoryConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: HelmRepositoryInstance) => {
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
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete Helm Repository instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showMessage(`Helm Repository instance "${name}" deleted`, 'success');
    } catch {
      showMessage('Failed to delete Helm Repository instance', 'error');
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

  const columns: ColumnsType<HelmRepositoryInstance> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'URL', dataIndex: 'url', key: 'url' },
    { title: 'Username', dataIndex: 'username', key: 'username' },
    {
      title: 'Default',
      key: 'is_default',
      render: (_: unknown, record: HelmRepositoryInstance) =>
        record.is_default ? 'Yes' : 'No',
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: HelmRepositoryInstance) => (
        <StatusChip statusFlag={record.status_flag as StatusFlag} statusText={record.status_text} />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: HelmRepositoryInstance) => (
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
          Helm Repository Instances
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
          Failed to load Helm Repository instances. Please try again later.
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
            locale={{ emptyText: 'No Helm Repository instances configured' }}
          />
        </Card>
      )}

      {dialog.open && (
        <HelmRepositoryDialog
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

// ─── Helm Repository Dialog ────────────────────────────────────────────────────

interface HelmRepositoryDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateHelmRepositoryInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateHelmRepositoryInstanceMutation>[0];
  showMessage: (message: string, severity: 'success' | 'error') => void;
}

function HelmRepositoryDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showMessage,
}: HelmRepositoryDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [url, setUrl] = useState((dialogState.defaultValues?.url as string) ?? '');
  const [username, setUsername] = useState((dialogState.defaultValues?.username as string) ?? '');
  const [password, setPassword] = useState((dialogState.defaultValues?.password as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true,
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true,
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false,
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
      const payload: HelmRepositoryInstanceCreate | HelmRepositoryInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        username: username.trim(),
        password: password.trim() || undefined,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as HelmRepositoryInstanceUpdate,
        }).unwrap();
        showMessage('Helm Repository instance updated', 'success');
      } else {
        await createInstance(payload as HelmRepositoryInstanceCreate).unwrap();
        showMessage('Helm Repository instance created', 'success');
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
      title={isEdit ? 'Edit Helm Repository Instance' : 'Add Helm Repository Instance'}
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
            placeholder="https://charts.example.com"
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
              e.g. https://charts.example.com
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

export default SettingsIntegrations;
