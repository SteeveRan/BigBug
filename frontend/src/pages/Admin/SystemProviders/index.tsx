/**
 * @file Admin/SystemProviders/index.tsx
 * @description System providers management page (`/admin/providers`). Loads
 *              providers with `category=system` (system providers are hidden from
 *              the general Settings→Providers grid) and offers test/edit/delete
 *              actions gated by `providers_system:write`.
 * @dependencies antd, @ant-design/icons, RTK Query, PermissionGate, StatusChip
 * @relatedFiles ./SystemProviderFormModal.tsx, ./DeleteSystemProviderModal.tsx
 */

import { useMemo, useState } from 'react';
import {
  App,
  Alert,
  Button,
  Card,
  Empty,
  Flex,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import {
  useGetProviderTypesQuery,
  useGetProvidersQuery,
  useUpdateProviderMutation,
  useTestProviderMutation,
  useListUsersQuery,
} from '../../../store/api';
import type {
  ProviderCategory,
  ProviderDirection,
  ProviderDomain,
  ProviderSubtype,
  ProviderTypeSpec,
  ResourceProvider,
  User,
} from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';
import { usePermissions } from '../../../hooks/usePermissions';
import { SystemProviderFormModal } from './SystemProviderFormModal';
import { DeleteSystemProviderModal } from './DeleteSystemProviderModal';

const DOMAIN_LABELS: Record<ProviderDomain, string> = {
  git: 'Git',
  docker: 'Docker',
  helm: 'Helm',
};

const DOMAIN_COLORS: Record<ProviderDomain, string> = {
  git: 'geekblue',
  docker: 'cyan',
  helm: 'purple',
};

const CATEGORY_LABELS: Record<ProviderCategory, string> = {
  system: 'System',
  public: 'Public',
  private: 'Private',
};

const CATEGORY_COLORS: Record<ProviderCategory, string> = {
  system: 'gold',
  public: 'green',
  private: 'default',
};

const DIRECTION_LABELS: Record<ProviderDirection, string> = {
  external: 'External',
  internal: 'Internal',
};

export function SystemProvidersPage() {
  const { message } = App.useApp();
  const { hasPermission } = usePermissions();

  const [editingProvider, setEditingProvider] = useState<ResourceProvider | undefined>(undefined);
  const [deleteProvider, setDeleteProvider] = useState<ResourceProvider | undefined>(undefined);
  const [testingId, setTestingId] = useState<number | undefined>(undefined);

  const { data: types = [] } = useGetProviderTypesQuery();
  const { data: users = [] } = useListUsersQuery(undefined, {
    skip: !hasPermission('users:read'),
  });

  const {
    data: rawProviders = [],
    isLoading,
    isError,
    refetch,
  } = useGetProvidersQuery(undefined);

  // Admin page surfaces both platform providers (category=system) and the
  // default providers (`is_default`) configured by the seed/admin. Ordinary
  // public/private providers stay on the general Settings→Providers grid.
  const providers = useMemo(
    () =>
      (rawProviders as ResourceProvider[]).filter(
        (p) => p.category === 'system' || p.is_default
      ),
    [rawProviders]
  );

  const [updateProvider] = useUpdateProviderMutation();
  const [testConnection] = useTestProviderMutation();

  const typeSpecs = useMemo(() => {
    const map = new Map<ProviderSubtype, ProviderTypeSpec>();
    for (const t of types as ProviderTypeSpec[]) map.set(t.subtype, t);
    return map;
  }, [types]);

  const getUserLabel = (record: ResourceProvider): string => {
    if (!record.owner_user_id) return '—';
    const owner = (users as User[]).find((u) => u.id === record.owner_user_id);
    return owner?.username ?? `#${record.owner_user_id}`;
  };

  const subtypeLabel = (record: ResourceProvider): string =>
    typeSpecs.get(record.subtype)?.label ?? record.subtype;

  const handleSetDefault = async (record: ResourceProvider, value: boolean) => {
    try {
      await updateProvider({ id: record.id, data: { is_default: value } }).unwrap();
      message.success(value ? 'Назначен по умолчанию' : 'Default снят');
    } catch (err) {
      message.error(err instanceof Error ? err.message : 'Не удалось обновить default');
    }
  };

  const handleTestConnection = async (record: ResourceProvider) => {
    if (testingId !== undefined) return;
    setTestingId(record.id);
    try {
      const result = await testConnection(record.id).unwrap();
      if (result.ok || result.status_flag === 0) {
        message.success(result.status_text ?? 'Connection successful');
      } else {
        message.error(result.status_text ?? 'Connection test failed');
      }
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Connection test failed');
    } finally {
      setTestingId(undefined);
    }
  };

  const columns = useMemo<ColumnsType<ResourceProvider>>(
    () => [
      {
        title: 'Label',
        key: 'label',
        width: 220,
        sorter: (a, b) => a.label.localeCompare(b.label),
        render: (_: unknown, record) => (
          <Flex vertical>
            <Space size={4}>
              <Typography.Text strong ellipsis={{ tooltip: record.label }}>
                {record.label}
              </Typography.Text>
              {record.is_default && <Tag color="blue">Default</Tag>}
              {record.is_protected && <Tag color="gold">Protected</Tag>}
            </Space>
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12 }}
              ellipsis={{ tooltip: record.name }}
            >
              {record.name}
            </Typography.Text>
          </Flex>
        ),
      },
      {
        title: 'Category',
        dataIndex: 'category',
        key: 'category',
        width: 100,
        sorter: (a, b) => a.category.localeCompare(b.category),
        render: (value: ProviderCategory) => (
          <Tag color={CATEGORY_COLORS[value]}>{CATEGORY_LABELS[value]}</Tag>
        ),
      },
      {
        title: 'Domain',
        dataIndex: 'domain',
        key: 'domain',
        width: 90,
        sorter: (a, b) => a.domain.localeCompare(b.domain),
        render: (value: ProviderDomain) => (
          <Tag color={DOMAIN_COLORS[value]}>{DOMAIN_LABELS[value]}</Tag>
        ),
      },
      {
        title: 'Subtype',
        dataIndex: 'subtype',
        key: 'subtype',
        width: 170,
        sorter: (a, b) => a.subtype.localeCompare(b.subtype),
        render: (_: string, record) => (
          <Typography.Text ellipsis={{ tooltip: record.subtype }}>
            {subtypeLabel(record)}
          </Typography.Text>
        ),
      },
      {
        title: 'Direction',
        dataIndex: 'direction',
        key: 'direction',
        width: 100,
        sorter: (a, b) => a.direction.localeCompare(b.direction),
        render: (value: ProviderDirection) => DIRECTION_LABELS[value],
      },
      {
        title: 'Status',
        key: 'status',
        width: 120,
        render: (_: unknown, record) => (
          <StatusChip
            statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
            statusText={record.status_text}
          />
        ),
      },
      {
        title: 'Default',
        key: 'default',
        width: 90,
        align: 'center',
        render: (_: unknown, record) => (
          <PermissionGate permission="providers_system:write">
            <Switch
              size="small"
              checked={record.is_default}
              onChange={(checked) => handleSetDefault(record, checked)}
            />
          </PermissionGate>
        ),
      },
      {
        title: 'Owner',
        key: 'owner',
        width: 110,
        render: (_: unknown, record) => <Typography.Text>{getUserLabel(record)}</Typography.Text>,
      },
      {
        title: 'Base URL',
        dataIndex: 'base_url',
        key: 'base_url',
        width: 200,
        render: (value: string | null) =>
          value ? (
            <Typography.Text style={{ fontSize: 12 }} ellipsis={{ tooltip: value }}>
              {value}
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary">—</Typography.Text>
          ),
      },
      {
        title: 'Actions',
        key: 'actions',
        align: 'right',
        width: 160,
        fixed: 'right',
        render: (_: unknown, record) => (
          <Space size={4}>
            <PermissionGate permission="providers_system:write">
              <Tooltip title="Test">
                <Button
                  size="small"
                  type="text"
                  icon={<PlayCircleOutlined />}
                  loading={testingId === record.id}
                  onClick={() => handleTestConnection(record)}
                />
              </Tooltip>
              <Tooltip title="Edit">
                <Button
                  size="small"
                  type="text"
                  icon={<EditOutlined />}
                  onClick={() => setEditingProvider(record)}
                />
              </Tooltip>
              {!record.is_protected && (
                <Tooltip title="Delete">
                  <Button
                    size="small"
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => setDeleteProvider(record)}
                  />
                </Tooltip>
              )}
            </PermissionGate>
          </Space>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [typeSpecs, users, testingId, hasPermission]
  );

  const scrollX = useMemo(() => {
    const width = columns.reduce((sum, col) => sum + (Number(col.width) || 0), 0);
    return Math.max(width + 32, 1200);
  }, [columns]);

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Flex vertical gap={4}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            System Providers
          </Typography.Title>
          <Typography.Text type="secondary">
            System-level and default resource providers (Git, Docker, Helm) managed by
            administrators.
          </Typography.Text>
        </Flex>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
          Refresh
        </Button>
      </Flex>

      {isLoading ? (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      ) : isError ? (
        <Alert title="Failed to load providers" type="error" showIcon />
      ) : (
        <Card>
          <Table
            columns={columns}
            dataSource={providers as ResourceProvider[]}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            scroll={{ x: scrollX }}
            locale={{ emptyText: <Empty description="No system or default providers configured" /> }}
          />
        </Card>
      )}

      <SystemProviderFormModal
        open={!!editingProvider}
        provider={editingProvider}
        onClose={() => setEditingProvider(undefined)}
      />
      <DeleteSystemProviderModal
        provider={deleteProvider}
        onClose={() => setDeleteProvider(undefined)}
      />
    </Flex>
  );
}

export default SystemProvidersPage;
