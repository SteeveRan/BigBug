/**
 * @file Admin/index.tsx
 * @description Admin page with two tabs: Users and Roles management.
 *              Roles tab provides full CRUD with 34 permission checkboxes
 *              grouped by resource, builtin-role protection, and delete confirmation.
 * @dependencies antd, @ant-design/icons, ../../store/api, ../../types, ../../components/PermissionGate
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
  Select,
  Switch,
  Checkbox,
  Tooltip,
  App,
  Tabs,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, DeleteOutlined, EditOutlined, LockOutlined } from '@ant-design/icons';

import type { Role, RoleCreate, RoleUpdate, User } from '../../types';
import {
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
  useGetAllRolesQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
} from '../../store/api';
import { PermissionGate } from '../../components/PermissionGate';

// ─── Permission groups (34 permissions in 9 resource groups) ────────────────

interface PermissionGroup {
  label: string;
  permissions: string[];
}

const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    label: 'Mirrors',
    permissions: ['mirrors:read', 'mirrors:write', 'mirrors:delete', 'mirrors:sync'],
  },
  {
    label: 'Projects',
    permissions: ['projects:read', 'projects:write', 'projects:delete'],
  },
  {
    label: 'Helm',
    permissions: ['helm:read', 'helm:write', 'helm:delete', 'helm:sync'],
  },
  {
    label: 'Docker',
    permissions: ['docker:read', 'docker:write', 'docker:delete', 'docker:sync'],
  },
  {
    label: 'Gold Images',
    permissions: [
      'gold_images:read',
      'gold_images:write',
      'gold_images:delete',
      'gold_images:build',
    ],
  },
  {
    label: 'App Images',
    permissions: ['app_images:read', 'app_images:write', 'app_images:delete', 'app_images:build'],
  },
  {
    label: 'Users',
    permissions: ['users:read', 'users:write', 'users:delete'],
  },
  {
    label: 'Roles',
    permissions: ['roles:read', 'roles:write', 'roles:delete'],
  },
  {
    label: 'System',
    permissions: [
      'system:settings',
      'system:audit',
      'system:integrations',
      'system:oidc_config',
      'pipelines:manage',
    ],
  },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Derive a human-readable label from a permission string like "mirrors:read" */
function permissionLabel(perm: string): string {
  const [resource, action] = perm.split(':');
  if (!action) return perm;
  return `${action} → ${resource}`;
}

/** Map MUI chip colour semantics to Ant Design Tag colour values */
function roleTagColor(role: string): string {
  if (role === 'admin') return 'red';
  if (role === 'operator') return 'orange';
  return 'default';
}

// ─── Users Tab ───────────────────────────────────────────────────────────────

function UsersTab() {
  const { message, modal } = App.useApp();
  const { data: users = [], isLoading } = useListUsersQuery();
  const [createUser] = useCreateUserMutation();
  const [updateUser] = useUpdateUserMutation();
  const [deleteUser] = useDeleteUserMutation();

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ username: '', email: '', password: '', roles: 'viewer' });
  const [submitting, setSubmitting] = useState(false);

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      await createUser({
        username: form.username,
        email: form.email,
        password: form.password,
        roles: [form.roles],
      }).unwrap();
      setCreateOpen(false);
      setForm({ username: '', email: '', password: '', roles: 'viewer' });
      message.success(`User "${form.username}" created successfully`);
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to create user')
          : 'Failed to create user';
      message.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (user: User) => {
    try {
      await updateUser({ id: user.id, data: { is_active: !user.is_active } }).unwrap();
      message.success(`User "${user.username}" ${user.is_active ? 'deactivated' : 'activated'}`);
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to update user')
          : 'Failed to update user';
      message.error(detail);
    }
  };

  const handleDelete = (user: User) => {
    modal.confirm({
      title: 'Delete User',
      content: `Are you sure you want to delete user "${user.username}"?`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await deleteUser(user.id).unwrap();
          message.success(`User "${user.username}" deleted`);
        } catch (err: unknown) {
          const detail =
            err && typeof err === 'object' && 'data' in err
              ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to delete user')
              : 'Failed to delete user';
          message.error(detail);
        }
      },
    });
  };

  const columns: ColumnsType<User> = [
    {
      title: 'Username',
      key: 'username',
      render: (_: unknown, record: User) => (
        <Typography.Text strong>{record.username}</Typography.Text>
      ),
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Roles',
      key: 'roles',
      render: (_: unknown, record: User) => (
        <Flex gap={4} wrap="wrap">
          {record.roles.map((role) => (
            <Tag key={role} color={roleTagColor(role)}>
              {role}
            </Tag>
          ))}
        </Flex>
      ),
    },
    {
      title: 'Active',
      key: 'active',
      render: (_: unknown, record: User) => (
        <Switch
          checked={record.is_active}
          onChange={() => handleToggleActive(record)}
          size="small"
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: User) => (
        <Tooltip title="Delete user">
          <Button
            size="small"
            danger
            type="text"
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record)}
          />
        </Tooltip>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* Header */}
      <Flex justify="space-between" align="center">
        <Typography.Title level={5} style={{ margin: 0 }}>
          User Management
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Add User
        </Button>
      </Flex>

      {/* Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={users as User[]}
          rowKey="id"
          loading={isLoading}
          pagination={false}
          size="small"
          locale={{ emptyText: 'No users found' }}
        />
      </Card>

      {/* Create User Modal */}
      <Modal
        title="Add User"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setCreateOpen(false)}>
            Cancel
          </Button>,
          <Button
            key="create"
            type="primary"
            loading={submitting}
            onClick={handleCreate}
            disabled={!form.username || !form.email || !form.password || submitting}
          >
            Create
          </Button>,
        ]}
      >
        <Flex vertical gap={16}>
          <Input
            placeholder="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
          />
          <Input
            placeholder="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
          <Input.Password
            placeholder="Password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />
          <Select
            value={form.roles}
            onChange={(v) => setForm({ ...form, roles: v })}
            options={[
              { label: 'Viewer', value: 'viewer' },
              { label: 'Operator', value: 'operator' },
              { label: 'Admin', value: 'admin' },
            ]}
            style={{ width: '100%' }}
          />
        </Flex>
      </Modal>
    </Flex>
  );
}

// ─── Roles Tab ───────────────────────────────────────────────────────────────

function RolesTab() {
  const { message } = App.useApp();
  const { data: roles = [], isLoading } = useGetAllRolesQuery();
  const [createRole] = useCreateRoleMutation();
  const [updateRole] = useUpdateRoleMutation();
  const [deleteRole] = useDeleteRoleMutation();

  // Create/Edit dialog
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [dialogName, setDialogName] = useState('');
  const [dialogDescription, setDialogDescription] = useState('');
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);

  // Delete confirmation dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingRole, setDeletingRole] = useState<Role | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // ─── Permission selection helpers ─────────────────────────────────────────

  const isGroupAllSelected = useCallback(
    (group: PermissionGroup): boolean => {
      return group.permissions.every((p) => selectedPermissions.includes(p));
    },
    [selectedPermissions]
  );

  const isGroupSomeSelected = useCallback(
    (group: PermissionGroup): boolean => {
      return group.permissions.some((p) => selectedPermissions.includes(p));
    },
    [selectedPermissions]
  );

  const handleToggleGroup = useCallback((group: PermissionGroup, select: boolean) => {
    setSelectedPermissions((prev) => {
      if (select) {
        const toAdd = group.permissions.filter((p) => !prev.includes(p));
        return [...prev, ...toAdd];
      }
      return prev.filter((p) => !group.permissions.includes(p));
    });
  }, []);

  // ─── Dialog handlers ──────────────────────────────────────────────────────

  const handleOpenCreate = () => {
    setEditingRole(null);
    setDialogName('');
    setDialogDescription('');
    setSelectedPermissions([]);
    setDialogOpen(true);
  };

  const handleOpenEdit = (role: Role) => {
    setEditingRole(role);
    setDialogName(role.name);
    setDialogDescription(role.description ?? '');
    setSelectedPermissions(role.permissions.map((p) => p.name));
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingRole(null);
  };

  const handleSaveRole = async () => {
    if (!dialogName.trim()) return;
    setIsSaving(true);
    try {
      if (editingRole) {
        const data: RoleUpdate = {
          name: dialogName.trim() !== editingRole.name ? dialogName.trim() : undefined,
          description:
            dialogDescription.trim() !== (editingRole.description ?? '')
              ? dialogDescription.trim() || null
              : undefined,
          permission_names: selectedPermissions,
        };
        await updateRole({ id: editingRole.id, data }).unwrap();
        message.success(`Role "${dialogName.trim()}" updated successfully`);
      } else {
        const data: RoleCreate = {
          name: dialogName.trim(),
          description: dialogDescription.trim() || undefined,
          permission_names: selectedPermissions,
        };
        await createRole(data).unwrap();
        message.success(`Role "${dialogName.trim()}" created successfully`);
      }
      handleCloseDialog();
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to save role')
          : 'Failed to save role';
      message.error(detail);
    } finally {
      setIsSaving(false);
    }
  };

  // ─── Delete handlers ──────────────────────────────────────────────────────

  const handleOpenDelete = (role: Role) => {
    setDeletingRole(role);
    setDeleteDialogOpen(true);
  };

  const handleCloseDelete = () => {
    setDeleteDialogOpen(false);
    setDeletingRole(null);
  };

  const handleConfirmDelete = async () => {
    if (!deletingRole) return;
    setIsDeleting(true);
    try {
      await deleteRole(deletingRole.id).unwrap();
      message.success(`Role "${deletingRole.name}" deleted successfully`);
      handleCloseDelete();
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to delete role')
          : 'Failed to delete role';
      message.error(detail);
    } finally {
      setIsDeleting(false);
    }
  };

  // ─── Table columns ────────────────────────────────────────────────────────

  const columns: ColumnsType<Role> = [
    {
      title: 'Name',
      key: 'name',
      render: (_: unknown, record: Role) => (
        <Flex align="center" gap={8}>
          {!record.is_custom && (
            <Tooltip title="Built-in role — cannot be modified">
              <LockOutlined style={{ color: 'rgba(0,0,0,0.45)' }} />
            </Tooltip>
          )}
          <Typography.Text strong>{record.name}</Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Description',
      key: 'description',
      render: (_: unknown, record: Role) => (
        <Typography.Text type="secondary">{record.description ?? '—'}</Typography.Text>
      ),
    },
    {
      title: 'Type',
      key: 'type',
      render: (_: unknown, record: Role) => (
        <Tag color={record.is_custom ? 'blue' : 'default'}>
          {record.is_custom ? 'Custom' : 'Builtin'}
        </Tag>
      ),
    },
    {
      title: 'Permissions',
      key: 'permissions',
      render: (_: unknown, record: Role) => <Tag>{record.permissions.length}</Tag>,
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: Role) => (
        <Flex gap={4} justify="flex-end">
          <PermissionGate permission="roles:write">
            <Tooltip title={record.is_custom ? 'Edit role' : 'Built-in roles cannot be edited'}>
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => handleOpenEdit(record)}
                disabled={!record.is_custom}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="roles:delete">
            <Tooltip title={record.is_custom ? 'Delete role' : 'Built-in roles cannot be deleted'}>
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleOpenDelete(record)}
                disabled={!record.is_custom}
              />
            </Tooltip>
          </PermissionGate>
        </Flex>
      ),
    },
  ];

  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: '40px 0' }}>
        <Spin />
      </Flex>
    );
  }

  return (
    <Flex vertical gap={16}>
      {/* Header */}
      <Flex justify="space-between" align="center">
        <Typography.Title level={5} style={{ margin: 0 }}>
          Role Management
        </Typography.Title>
        <PermissionGate permission="roles:write">
          <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>
            Create Role
          </Button>
        </PermissionGate>
      </Flex>

      {/* Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={roles as Role[]}
          rowKey="id"
          pagination={false}
          size="small"
          locale={{ emptyText: 'No roles found' }}
        />
      </Card>

      {/* ─── Create / Edit Role Modal ──────────────────────────────────────── */}
      <Modal
        title={editingRole ? `Edit Role: ${editingRole.name}` : 'Create Role'}
        open={dialogOpen}
        onCancel={handleCloseDialog}
        width={720}
        footer={[
          <Button key="cancel" onClick={handleCloseDialog} disabled={isSaving}>
            Cancel
          </Button>,
          <Button
            key="save"
            type="primary"
            loading={isSaving}
            onClick={handleSaveRole}
            disabled={!dialogName.trim() || isSaving}
          >
            {editingRole ? 'Save' : 'Create'}
          </Button>,
        ]}
      >
        <Flex vertical gap={16}>
          {/* Name & Description */}
          <Flex gap={12} wrap="wrap">
            <div style={{ flex: '1 1 240px' }}>
              <Input
                placeholder="Name"
                value={dialogName}
                onChange={(e) => setDialogName(e.target.value)}
                disabled={isSaving}
              />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Lowercase, alphanumeric with underscores (e.g. dev_lead)
              </Typography.Text>
            </div>
            <div style={{ flex: '2 1 360px' }}>
              <Input
                placeholder="Description"
                value={dialogDescription}
                onChange={(e) => setDialogDescription(e.target.value)}
                disabled={isSaving}
              />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Optional. Human-readable description of the role.
              </Typography.Text>
            </div>
          </Flex>

          {/* Permissions grouped by resource */}
          <Flex vertical gap={12}>
            <Typography.Text strong>Permissions</Typography.Text>
            {PERMISSION_GROUPS.map((group) => (
              <Card
                key={group.label}
                size="small"
                title={<Typography.Text strong>{group.label}</Typography.Text>}
                extra={
                  <Flex gap={4}>
                    <Button
                      size="small"
                      type="link"
                      onClick={() => handleToggleGroup(group, true)}
                      disabled={isSaving || isGroupAllSelected(group)}
                    >
                      Select All
                    </Button>
                    <Button
                      size="small"
                      type="link"
                      onClick={() => handleToggleGroup(group, false)}
                      disabled={isSaving || !isGroupSomeSelected(group)}
                    >
                      Deselect All
                    </Button>
                  </Flex>
                }
              >
                <Checkbox.Group
                  style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}
                  options={group.permissions.map((perm) => ({
                    label: permissionLabel(perm),
                    value: perm,
                  }))}
                  value={selectedPermissions.filter((p) => group.permissions.includes(p))}
                  onChange={(checkedValues: string[]) => {
                    const otherPerms = selectedPermissions.filter(
                      (p) => !group.permissions.includes(p)
                    );
                    setSelectedPermissions([...otherPerms, ...checkedValues]);
                  }}
                />
              </Card>
            ))}
          </Flex>
        </Flex>
      </Modal>

      {/* ─── Delete Confirmation Modal ─────────────────────────────────────── */}
      <Modal
        title="Delete Role"
        open={deleteDialogOpen}
        onCancel={handleCloseDelete}
        onOk={handleConfirmDelete}
        confirmLoading={isDeleting}
        okText="Delete"
        okButtonProps={{ danger: true }}
        cancelText="Cancel"
        cancelButtonProps={{ disabled: isDeleting }}
      >
        <Typography.Text>
          Are you sure you want to delete role &ldquo;{deletingRole?.name}&rdquo;?
        </Typography.Text>
      </Modal>
    </Flex>
  );
}

// ─── Main AdminPage ──────────────────────────────────────────────────────────

export function AdminPage() {
  return (
    <Flex vertical gap={16}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          Admin
        </Typography.Title>
        <Typography.Text type="secondary">
          Manage users, roles, and permissions for the BigBug platform.
        </Typography.Text>
      </div>

      <Tabs
        defaultActiveKey="users"
        items={[
          { key: 'users', label: 'Users', children: <UsersTab /> },
          { key: 'roles', label: 'Roles', children: <RolesTab /> },
        ]}
      />
    </Flex>
  );
}

export default AdminPage;
