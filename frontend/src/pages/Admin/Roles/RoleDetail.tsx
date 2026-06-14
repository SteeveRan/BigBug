/**
 * @file Admin/Roles/RoleDetail.tsx
 * @description Role detail page with tabs: Permissions (read-only), Users (assigned users list),
 *              Source Groups scope, Credentials scope, and Sync Groups scope management.
 *              Uses Transfer component for Sync Groups (atomic setRoleScope on save).
 * @dependencies antd, @ant-design/icons, react-router, RTK Query
 * @relatedFiles ./index.tsx, ./RoleModal.tsx, ../../../store/api.ts, ../../../types/index.ts
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Spin,
  Tabs,
  Checkbox,
  Tag,
  Select,
  Transfer,
  App,
  Alert,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ArrowLeftOutlined, MinusCircleOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router';

import type { TabsProps } from 'antd';
import type {
  Role,
  Permission,
  SyncGroup,
  SourceGroup,
  SourceProvider,
  User,
} from '../../../types';
import {
  useGetAllRolesQuery,
  useGetAllPermissionsQuery,
  useGetRoleUsersQuery,
  useGetRoleScopeQuery,
  useRemoveRoleScopeItemMutation,
  useSetRoleScopeMutation,
  useAddRoleScopeItemMutation,
  useGetSyncGroupsQuery,
  useGetSourceProvidersQuery,
  useGetSourceGroupsQuery,
} from '../../../store/api';

// ── Helpers ───────────────────────────────────────────────────────────────────

function permissionLabel(perm: string): string {
  const [resource, action] = perm.split(':');
  if (!action) return perm;
  return `${action} → ${resource}`;
}

function roleTagColor(role: string): string {
  if (role === 'admin') return 'red';
  if (role === 'operator') return 'orange';
  return 'default';
}

// ── Permissions Tab ───────────────────────────────────────────────────────────

function PermissionsTab({ role }: { role: Role }) {
  const { data: allPermissions = [] } = useGetAllPermissionsQuery();
  const assignedNames = useMemo(() => new Set(role.permissions.map((p) => p.name)), [role]);

  return (
    <Flex vertical gap={12}>
      <Typography.Text type="secondary">
        This role has the following permissions. Permissions can be modified via the Edit Role
        dialog.
      </Typography.Text>
      <Card size="small" title="Assigned Permissions">
        <Checkbox.Group
          style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}
          disabled
          options={allPermissions.map((p: Permission) => ({
            label: permissionLabel(p.name),
            value: p.name,
          }))}
          value={[...assignedNames]}
        />
      </Card>
    </Flex>
  );
}

// ── Users Tab ─────────────────────────────────────────────────────────────────

function UsersTab({ roleId }: { roleId: number }) {
  const { data: users = [], isLoading } = useGetRoleUsersQuery(roleId);

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
          {record.roles.map((r) => (
            <Tag key={r} color={roleTagColor(r)}>
              {r}
            </Tag>
          ))}
        </Flex>
      ),
    },
    {
      title: 'Active',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      align: 'center',
      render: (is_active: boolean) => (
        <Tag color={is_active ? 'green' : 'default'}>{is_active ? 'Yes' : 'No'}</Tag>
      ),
    },
  ];

  return (
    <Flex vertical gap={12}>
      <Typography.Text type="secondary">
        Users directly assigned to this role ({users.length} total).
      </Typography.Text>
      <Table
        columns={columns}
        dataSource={users as User[]}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        size="small"
        locale={{ emptyText: 'No users assigned to this role' }}
      />
    </Flex>
  );
}

// ── Scope Tabs ────────────────────────────────────────────────────────────────

interface TransferItem {
  key: string;
  title: string;
  description?: string;
}

type ScopeType = 'source-groups' | 'credentials' | 'sync-groups';

interface ScopeTabProps {
  roleId: number;
  scopeType: ScopeType;
  title: string;
  availableItems: TransferItem[];
}

function ScopeTab({ roleId, scopeType, title, availableItems }: ScopeTabProps) {
  const { message } = App.useApp();

  const { data: scope, isLoading } = useGetRoleScopeQuery({ roleId, scopeType }, { skip: !roleId });

  const [removeScopeItem] = useRemoveRoleScopeItemMutation();
  const [setScope] = useSetRoleScopeMutation();
  const [addScopeItem] = useAddRoleScopeItemMutation();

  // Derive current scope IDs based on scopeType
  const currentIds = useMemo(() => {
    if (!scope) return [];
    switch (scopeType) {
      case 'source-groups':
        return scope.source_group_ids ?? [];
      case 'credentials':
        return scope.credential_ids ?? [];
      case 'sync-groups':
        return scope.sync_group_ids ?? [];
      default:
        return [];
    }
  }, [scope, scopeType]);

  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Sync selectedIds when scope data loads or roleId/scopeType changes
  useEffect(() => {
    setSelectedIds(currentIds.map(String));
  }, [currentIds, roleId, scopeType]);

  const handleTransferChange = useCallback(
    (targetKeys: string[], _direction: string, _moveKeys: string[]) => {
      setSelectedIds(targetKeys);
    },
    []
  );

  const handleSaveTransfer = async () => {
    try {
      const numericIds = selectedIds.map(Number).filter((n) => !isNaN(n));
      switch (scopeType) {
        case 'source-groups':
          await setScope({
            roleId,
            scopeType,
            data: { source_group_ids: numericIds },
          }).unwrap();
          break;
        case 'credentials':
          await setScope({
            roleId,
            scopeType,
            data: { credential_ids: numericIds },
          }).unwrap();
          break;
        case 'sync-groups':
          await setScope({
            roleId,
            scopeType,
            data: { sync_group_ids: numericIds },
          }).unwrap();
          break;
      }
      message.success(`${title} scope updated`);
    } catch {
      message.error(`Failed to update ${title} scope`);
    }
  };

  // ── Remove single item ────────────────────────────────────────────────────
  const handleRemove = async (itemId: number) => {
    try {
      await removeScopeItem({
        roleId,
        scopeType,
        itemId,
      }).unwrap();
      message.success(`${title} item removed`);
    } catch {
      message.error(`Failed to remove ${title} item`);
    }
  };

  // ── Add single item via Select ─────────────────────────────────────────────
  const [addValue, setAddValue] = useState<number | undefined>(undefined);

  const handleAdd = async () => {
    if (addValue === undefined) return;
    try {
      const item: Record<string, number> = {};
      switch (scopeType) {
        case 'source-groups':
          item.source_group_id = addValue;
          break;
        case 'credentials':
          item.credential_id = addValue;
          break;
        case 'sync-groups':
          item.sync_group_id = addValue;
          break;
      }
      const scopeItem = item as {
        source_group_id?: number;
        credential_id?: number;
        sync_group_id?: number;
      };
      await addScopeItem({
        roleId,
        scopeType,
        item: scopeItem,
      }).unwrap();
      message.success(`${title} item added`);
      setAddValue(undefined);
    } catch {
      message.error(`Failed to add ${title} item`);
    }
  };

  // Filter available items to those not already in scope
  const notAssigned = useMemo(
    () => availableItems.filter((item) => !currentIds.includes(Number(item.key))),
    [availableItems, currentIds]
  );

  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: '40px 0' }}>
        <Spin />
      </Flex>
    );
  }

  return (
    <Flex vertical gap={16}>
      {/* ── Current scope as tags ───────────────────────────────────────────── */}
      <Card size="small" title={`Current ${title}`}>
        {currentIds.length === 0 ? (
          <Typography.Text type="secondary">No {title.toLowerCase()} assigned.</Typography.Text>
        ) : (
          <Flex gap={8} wrap="wrap">
            {currentIds.map((id) => {
              const found = availableItems.find((item) => Number(item.key) === id);
              return (
                <Tag
                  key={id}
                  closable
                  onClose={(e) => {
                    e.preventDefault();
                    handleRemove(id);
                  }}
                  closeIcon={<MinusCircleOutlined />}
                >
                  {found?.title ?? `ID: ${id}`}
                </Tag>
              );
            })}
          </Flex>
        )}
      </Card>

      {/* ── Add single item ─────────────────────────────────────────────────── */}
      <Card size="small" title={`Add ${title.slice(0, -1).toLowerCase()}`}>
        <Flex gap={8}>
          <Select
            style={{ flex: 1 }}
            placeholder={`Select ${title.slice(0, -1).toLowerCase()} to add...`}
            value={addValue}
            onChange={setAddValue}
            showSearch
            optionFilterProp="label"
            options={notAssigned.map((item) => ({
              label: item.description ? `${item.title} (${item.description})` : item.title,
              value: Number(item.key),
            }))}
            notFoundContent="No more items available"
          />
          <Button type="primary" onClick={handleAdd} disabled={addValue === undefined}>
            Add
          </Button>
        </Flex>
      </Card>

      {/* ── Transfer for bulk management ─────────────────────────────────────── */}
      <Card size="small" title={`Bulk Manage ${title}`}>
        <Transfer
          dataSource={availableItems}
          targetKeys={currentIds.map(String)}
          onChange={handleTransferChange}
          render={(item) => item.title}
          styles={{
            section: {
              width: 300,
              height: 300,
            },
          }}
          titles={['Available', 'Assigned']}
          showSearch
          filterOption={(inputValue, item) =>
            item.title.toLowerCase().includes(inputValue.toLowerCase())
          }
          style={{ marginBottom: 12 }}
        />
        <Button type="primary" onClick={handleSaveTransfer}>
          Save {title} Scope
        </Button>
      </Card>
    </Flex>
  );
}

// ── Main RoleDetailPage ────────────────────────────────────────────────────────

const RoleDetailPage = () => {
  const { roleId } = useParams<{ roleId: string }>();
  const navigate = useNavigate();
  const numericId = Number(roleId);

  const { data: roles = [], isLoading: isRoleLoading, isError } = useGetAllRolesQuery();

  const role = useMemo(() => roles.find((r: Role) => r.id === numericId), [roles, numericId]);

  // Load providers and their source groups for Source Groups scope tab
  const { data: providers = [] } = useGetSourceProvidersQuery();

  // Load source groups from the first available provider
  const typedProviders = providers as SourceProvider[];
  const firstProviderId = typedProviders.length > 0 ? typedProviders[0].id : 0;
  const { data: sourceGroupsList = [] } = useGetSourceGroupsQuery(firstProviderId, {
    skip: !firstProviderId,
  });

  // Load sync groups
  const { data: syncGroupsList = [] } = useGetSyncGroupsQuery();

  // Build transfer items for Source Groups
  const allSourceGroupItems: TransferItem[] = useMemo(() => {
    return (sourceGroupsList as SourceGroup[]).map((g) => ({
      key: String(g.id),
      title: g.name || g.full_name,
      description: g.description || undefined,
    }));
  }, [sourceGroupsList]);

  // Build transfer items for Sync Groups
  const syncGroupItems: TransferItem[] = useMemo(() => {
    return (syncGroupsList as SyncGroup[]).map((g) => ({
      key: String(g.id),
      title: g.name,
      description: g.description || undefined,
    }));
  }, [syncGroupsList]);

  // Build transfer items for Credentials (from integration instances)
  // Exclude providers without a linked credential (credential_id can be null)
  const credentialItems: TransferItem[] = useMemo(() => {
    return typedProviders
      .filter((p) => p.credential_id != null)
      .map((p) => ({
        key: String(p.credential_id!),
        title: p.credential?.name ?? `Credential #${p.credential_id!}`,
        description: p.label,
      }));
  }, [typedProviders]);

  if (isRoleLoading) {
    return (
      <Flex justify="center" style={{ padding: '40px 0' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  if (isError || !role) {
    return (
      <Flex vertical gap={16}>
        <Flex align="center" gap={8}>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/roles')}>
            Back to Roles
          </Button>
        </Flex>
        <Alert
          message="Role Not Found"
          description={`Role with ID ${roleId} was not found.`}
          type="error"
          showIcon
        />
      </Flex>
    );
  }

  const tabItems: TabsProps['items'] = [
    {
      key: 'permissions',
      label: 'Permissions',
      children: <PermissionsTab role={role} />,
    },
    {
      key: 'users',
      label: 'Users',
      children: <UsersTab roleId={numericId} />,
    },
    {
      key: 'source-groups',
      label: 'Source Groups',
      children: (
        <ScopeTab
          roleId={numericId}
          scopeType="source-groups"
          title="Source Groups"
          availableItems={allSourceGroupItems}
        />
      ),
    },
    {
      key: 'credentials',
      label: 'Credentials',
      children: (
        <ScopeTab
          roleId={numericId}
          scopeType="credentials"
          title="Credentials"
          availableItems={credentialItems}
        />
      ),
    },
    {
      key: 'sync-groups',
      label: 'Sync Groups',
      children: (
        <ScopeTab
          roleId={numericId}
          scopeType="sync-groups"
          title="Sync Groups"
          availableItems={syncGroupItems}
        />
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex align="center" gap={8} wrap="wrap">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/roles')}>
          Back to Roles
        </Button>
      </Flex>

      <Card>
        <Flex vertical gap={4}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            Role: {role.name}
          </Typography.Title>
          <Typography.Text type="secondary">
            {role.description ?? 'No description provided'}
          </Typography.Text>
        </Flex>
      </Card>

      {/* ── Tabs ────────────────────────────────────────────────────────────── */}
      <Card>
        <Tabs defaultActiveKey="permissions" items={tabItems} />
      </Card>
    </Flex>
  );
};

export default RoleDetailPage;
