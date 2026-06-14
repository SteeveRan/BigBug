/**
 * @file Admin/index.tsx
 * @description Admin page for Users management (create, toggle active, delete).
 * @dependencies antd, @ant-design/icons, ../../store/api, ../../types
 * @relatedFiles ../../store/api.ts, ../../types/index.ts
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
  Switch,
  Tooltip,
  App,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

import type { User } from '../../types';
import {
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
} from '../../store/api';

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Map MUI chip colour semantics to Ant Design Tag colour values */
function roleTagColor(role: string): string {
  if (role === 'admin') return 'red';
  if (role === 'operator') return 'orange';
  return 'default';
}

// ─── AdminPage (Users only) ──────────────────────────────────────────────────

export function AdminPage() {
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
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          Users
        </Typography.Title>
        <Typography.Text type="secondary">
          Manage user accounts for the BigBug platform.
        </Typography.Text>
      </div>

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

export default AdminPage;
