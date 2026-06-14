/**
 * @file Admin/Roles/index.tsx
 * @description Roles list page with table, create/edit modal, and delete.
 *              Shows builtin indicator (LockOutlined), Type column (Builtin/Custom),
 *              users_count, and blocks edit/delete for built-in roles.
 * @dependencies antd, @ant-design/icons, ../../../store/api, ../../../components/PermissionGate
 * @relatedFiles ./RoleModal.tsx, ../../../store/api.ts, ../../../types/index.ts
 */

import { useState, useCallback } from 'react';
import { Card, Typography, Button, Table, Flex, Spin, App, Tooltip, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router';

import type { Role } from '../../../types';
import { useGetAllRolesQuery, useDeleteRoleMutation } from '../../../store/api';
import { PermissionGate } from '../../../components/PermissionGate';
import { RoleModal } from './RoleModal';

const RolesPage = () => {
  const { message, modal } = App.useApp();
  const navigate = useNavigate();

  const { data: roles = [], isLoading, isError } = useGetAllRolesQuery();
  const [deleteRole, { isLoading: isDeleting }] = useDeleteRoleMutation();

  const [modalOpen, setModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | undefined>(undefined);

  const handleOpenCreate = useCallback(() => {
    setEditingRole(undefined);
    setModalOpen(true);
  }, []);

  const handleOpenEdit = useCallback((role: Role) => {
    setEditingRole(role);
    setModalOpen(true);
  }, []);

  const handleCloseModal = useCallback(() => {
    setModalOpen(false);
    setEditingRole(undefined);
  }, []);

  const handleDelete = useCallback(
    (role: Role) => {
      modal.confirm({
        title: 'Delete Role',
        content: `Are you sure you want to delete role "${role.name}"?`,
        okText: 'Delete',
        okType: 'danger',
        cancelText: 'Cancel',
        onOk: async () => {
          try {
            await deleteRole(role.id).unwrap();
            message.success(`Role "${role.name}" deleted`);
          } catch {
            message.error(`Failed to delete role "${role.name}"`);
          }
        },
      });
    },
    [deleteRole, message, modal]
  );

  const columns: ColumnsType<Role> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Role) => (
        <Flex align="center" gap={8}>
          {!record.is_custom && <LockOutlined style={{ color: '#1677ff' }} />}
          <Typography.Text strong>{name}</Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'is_custom',
      key: 'type',
      width: 100,
      render: (is_custom: boolean) => (
        <Tag color={is_custom ? 'blue' : 'gold'}>{is_custom ? 'Custom' : 'Builtin'}</Tag>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string | null) => (
        <Typography.Text type="secondary">{desc ?? '—'}</Typography.Text>
      ),
    },
    {
      title: 'Users',
      dataIndex: 'users_count',
      key: 'users_count',
      width: 80,
      align: 'center',
      render: (count: number | undefined) => <Typography.Text>{count ?? 0}</Typography.Text>,
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 120,
      render: (_: unknown, record: Role) => (
        <Flex gap={4} justify="flex-end">
          <PermissionGate permission="roles:write">
            <Tooltip title={record.is_custom ? 'Edit role' : 'Built-in roles cannot be edited'}>
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                disabled={!record.is_custom}
                onClick={(e) => {
                  e.stopPropagation();
                  handleOpenEdit(record);
                }}
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
                disabled={!record.is_custom || isDeleting}
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(record);
                }}
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
        <Spin size="large" />
      </Flex>
    );
  }

  if (isError) {
    return (
      <Flex vertical gap={16}>
        <Flex justify="space-between" align="center">
          <Typography.Title level={4} style={{ margin: 0 }}>
            Roles
          </Typography.Title>
        </Flex>
        <Card>
          <Typography.Text type="danger">
            Failed to load roles. Please try again later.
          </Typography.Text>
        </Card>
      </Flex>
    );
  }

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Roles
        </Typography.Title>
        <PermissionGate permission="roles:write">
          <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>
            Create Role
          </Button>
        </PermissionGate>
      </Flex>

      {/* ── Table ───────────────────────────────────────────────────────────── */}
      <Card>
        <Table
          columns={columns}
          dataSource={roles as Role[]}
          rowKey="id"
          loading={isLoading}
          pagination={false}
          size="small"
          locale={{ emptyText: 'No roles found' }}
          onRow={(record) => ({
            onClick: () => navigate(`/admin/roles/${record.id}`),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      {/* ── Create / Edit Modal ─────────────────────────────────────────────── */}
      <RoleModal open={modalOpen} role={editingRole} onClose={handleCloseModal} />
    </Flex>
  );
};

export default RolesPage;
