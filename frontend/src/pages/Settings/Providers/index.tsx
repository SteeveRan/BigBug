/**
 * @file Settings/Providers/index.tsx
 * @description Unified Providers V3 page (`/settings/providers`). A single grid with
 *              domain/category/direction tabs and a filter row. Private providers are
 *              personal (owner=me), system providers are read-only without
 *              `providers_system:write`.
 * @dependencies antd, @ant-design/icons, react-router, RTK Query, PermissionGate, StatusChip
 * @relatedFiles ./ProviderFormModal.tsx, ./TestConnectionModal.tsx, ./DeleteProviderModal.tsx,
 *               ./CredentialAssignModal.tsx, ./ShareProviderModal.tsx
 */

import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import {
  App,
  Alert,
  Button,
  Card,
  Empty,
  Flex,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  KeyOutlined,
  ShareAltOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import {
  useGetProviderTypesQuery,
  useGetProvidersQuery,
  useGetProviderUsageQuery,
  useUpdateProviderMutation,
} from '../../../store/api';
import type {
  ProviderCategory,
  ProviderDirection,
  ProviderDomain,
  ResourceProvider,
  ProviderTypeSpec,
} from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';
import { usePermissions } from '../../../hooks/usePermissions';
import { ProviderFormModal } from './ProviderFormModal';
import { TestConnectionModal } from './TestConnectionModal';
import { DeleteProviderModal } from './DeleteProviderModal';
import { CredentialAssignModal } from './CredentialAssignModal';
import { ShareProviderModal } from './ShareProviderModal';

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

interface TabConfig {
  key: string;
  label: string;
  domain?: ProviderDomain;
  category?: ProviderCategory;
  owner?: 'me';
}

const TABS: TabConfig[] = [
  { key: 'all', label: 'All' },
  { key: 'git', label: 'Git', domain: 'git' },
  { key: 'docker', label: 'Docker', domain: 'docker' },
  { key: 'helm', label: 'Helm', domain: 'helm' },
  { key: 'mine', label: 'My providers', owner: 'me', category: 'private' },
  { key: 'system', label: 'System', category: 'system' },
];

export function ProvidersPage() {
  const { message } = App.useApp();
  const { hasPermission } = usePermissions();
  const [searchParams] = useSearchParams();

  const [activeTab, setActiveTab] = useState<string>('all');
  const [domain, setDomain] = useState<ProviderDomain | undefined>(
    () => (searchParams.get('domain') as ProviderDomain) || undefined
  );
  const [subtype, setSubtype] = useState<string | undefined>();
  const [category, setCategory] = useState<ProviderCategory | undefined>();
  const [direction, setDirection] = useState<ProviderDirection | undefined>(
    () => (searchParams.get('direction') as ProviderDirection) || undefined
  );
  const [search, setSearch] = useState<string>('');
  const [onlyActive, setOnlyActive] = useState<boolean>(false);

  // Modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ResourceProvider | undefined>(undefined);
  const [testProvider, setTestProvider] = useState<ResourceProvider | undefined>(undefined);
  const [deleteProvider, setDeleteProvider] = useState<ResourceProvider | undefined>(undefined);
  const [credentialProvider, setCredentialProvider] = useState<ResourceProvider | undefined>(
    undefined
  );
  const [shareProvider, setShareProvider] = useState<ResourceProvider | undefined>(undefined);
  const [usageProvider, setUsageProvider] = useState<ResourceProvider | undefined>(undefined);

  const {
    data: types = [],
    isLoading: typesLoading,
    isError: typesError,
  } = useGetProviderTypesQuery();

  const providerParams = useMemo(() => {
    const tab = TABS.find((t) => t.key === activeTab);
    const effectiveDomain = domain ?? tab?.domain;
    const effectiveCategory = category ?? tab?.category;
    const effectiveDirection = direction;
    const owner = tab?.owner;
    const params: Record<string, string> = {};
    if (effectiveDomain) params.domain = effectiveDomain;
    if (effectiveCategory) params.category = effectiveCategory;
    if (effectiveDirection) params.direction = effectiveDirection;
    if (owner) params.owner = owner;
    if (subtype) params.subtype = subtype;
    return params;
  }, [activeTab, domain, subtype, category, direction]);

  const {
    data: rawProviders = [],
    isLoading,
    isError,
    refetch,
  } = useGetProvidersQuery(providerParams);

  // Client-side filtering for search/active-only (not part of the backend query contract).
  const providers = useMemo(() => {
    let list = rawProviders as ResourceProvider[];
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (p) => p.label.toLowerCase().includes(q) || p.name.toLowerCase().includes(q)
      );
    }
    if (onlyActive) {
      list = list.filter((p) => p.is_active);
    }
    return list;
  }, [rawProviders, search, onlyActive]);
  const [updateProvider] = useUpdateProviderMutation();

  const typeOptions = useMemo(() => {
    return types.map((t: ProviderTypeSpec) => ({ label: t.label, value: t.subtype }));
  }, [types]);

  const handleSetDefault = async (record: ResourceProvider, value: boolean) => {
    try {
      await updateProvider({ id: record.id, data: { is_default: value } }).unwrap();
      message.success(value ? 'Назначен по умолчанию' : 'Default снят');
    } catch (err) {
      message.error(err instanceof Error ? err.message : 'Не удалось обновить default');
    }
  };

  const columns: ColumnsType<ResourceProvider> = [
    {
      title: 'Label',
      key: 'label',
      sorter: (a, b) => a.label.localeCompare(b.label),
      render: (_: unknown, record) => (
        <Flex vertical>
          <Space size={4}>
            <Typography.Text strong>{record.label}</Typography.Text>
            {record.is_default && <Tag color="blue">Default</Tag>}
            {record.is_protected && <Tag color="gold">Protected</Tag>}
          </Space>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.name}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Domain',
      dataIndex: 'domain',
      key: 'domain',
      sorter: (a, b) => a.domain.localeCompare(b.domain),
      render: (value: ProviderDomain) => (
        <Tag color={DOMAIN_COLORS[value]}>{DOMAIN_LABELS[value]}</Tag>
      ),
    },
    {
      title: 'Subtype',
      dataIndex: 'subtype',
      key: 'subtype',
      sorter: (a, b) => a.subtype.localeCompare(b.subtype),
      render: (value: string, record) => (
        <Space size={4}>
          <Tag>{value}</Tag>
          {record.domain === 'docker' && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              OCI
            </Typography.Text>
          )}
        </Space>
      ),
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      sorter: (a, b) => a.category.localeCompare(b.category),
      render: (value: ProviderCategory) => (
        <Tag color={CATEGORY_COLORS[value]}>{CATEGORY_LABELS[value]}</Tag>
      ),
    },
    {
      title: 'Direction',
      dataIndex: 'direction',
      key: 'direction',
      sorter: (a, b) => a.direction.localeCompare(b.direction),
      render: (value: ProviderDirection) => DIRECTION_LABELS[value],
    },
    {
      title: 'Visibility',
      dataIndex: 'visibility',
      key: 'visibility',
      render: (value: string, record) => {
        if (value === 'team') return <Tag color="blue">Team · {record.team_name ?? '—'}</Tag>;
        if (value === 'public') return <Tag color="green">Public</Tag>;
        return <Tag>Private</Tag>;
      },
    },
    {
      title: 'Status',
      key: 'status',
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
        <PermissionGate permission="providers:write">
          <Switch
            size="small"
            checked={record.is_default}
            onChange={(checked) => handleSetDefault(record, checked)}
          />
        </PermissionGate>
      ),
    },
    {
      title: 'Credential',
      key: 'credential',
      width: 110,
      align: 'center',
      render: (_: unknown, record) => (
        <PermissionGate permission="providers:write">
          <Tooltip title={record.has_credential ? 'Credential assigned' : 'Assign credential'}>
            <Button
              size="small"
              type={record.has_credential ? 'primary' : 'text'}
              icon={<KeyOutlined />}
              onClick={() => setCredentialProvider(record)}
            />
          </Tooltip>
        </PermissionGate>
      ),
    },
    {
      title: 'Owner',
      key: 'owner',
      render: (_: unknown, record) => (
        <Typography.Text>{record.owner_user_id ? `#${record.owner_user_id}` : '—'}</Typography.Text>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 240,
      render: (_: unknown, record) => {
        const canMutate = !record.is_protected && hasPermission('providers:write');
        return (
          <Space size={4}>
            <PermissionGate permission="providers:use">
              <Tooltip title="Test">
                <Button
                  size="small"
                  type="text"
                  icon={<PlayCircleOutlined />}
                  onClick={() => setTestProvider(record)}
                />
              </Tooltip>
            </PermissionGate>
            {canMutate && (
              <Tooltip title="Edit">
                <Button
                  size="small"
                  type="text"
                  icon={<EditOutlined />}
                  onClick={() => {
                    setEditingProvider(record);
                    setFormOpen(true);
                  }}
                />
              </Tooltip>
            )}
            <PermissionGate permission="providers:share">
              {record.visibility !== 'team' && record.category !== 'system' && (
                <Tooltip title="Share">
                  <Button
                    size="small"
                    type="text"
                    icon={<ShareAltOutlined />}
                    onClick={() => setShareProvider(record)}
                  />
                </Tooltip>
              )}
            </PermissionGate>
            <PermissionGate permission="providers:read">
              <Tooltip title="Usage">
                <Button
                  size="small"
                  type="text"
                  icon={<BarChartOutlined />}
                  onClick={() => setUsageProvider(record)}
                />
              </Tooltip>
            </PermissionGate>
            {hasPermission('providers:delete') && canMutate && (
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
          </Space>
        );
      },
    },
  ];

  const onTabChange = (key: string) => {
    setActiveTab(key);
    const tab = TABS.find((t) => t.key === key);
    setDomain(tab?.domain);
    setCategory(tab?.category);
  };

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Flex vertical gap={4}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Providers
          </Typography.Title>
          <Typography.Text type="secondary">
            Unified resource providers (Git, Docker, Helm) with personal, public and system scopes.
          </Typography.Text>
        </Flex>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
            Refresh
          </Button>
          <PermissionGate permission="providers:write">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingProvider(undefined);
                setFormOpen(true);
              }}
            >
              Create provider
            </Button>
          </PermissionGate>
        </Space>
      </Flex>

      {/* ── Filters ──────────────────────────────────────────────────────── */}
      <Flex gap={8} wrap="wrap">
        <Select
          style={{ width: 140 }}
          allowClear
          placeholder="Domain"
          value={domain}
          onChange={(v) => setDomain(v)}
          options={[
            { label: 'Git', value: 'git' },
            { label: 'Docker', value: 'docker' },
            { label: 'Helm', value: 'helm' },
          ]}
        />
        <Select
          style={{ width: 180 }}
          allowClear
          placeholder="Subtype"
          value={subtype}
          onChange={(v) => setSubtype(v)}
          options={typeOptions}
        />
        <Select
          style={{ width: 140 }}
          allowClear
          placeholder="Category"
          value={category}
          onChange={(v) => setCategory(v)}
          options={[
            { label: 'System', value: 'system' },
            { label: 'Public', value: 'public' },
            { label: 'Private', value: 'private' },
          ]}
        />
        <Select
          style={{ width: 140 }}
          allowClear
          placeholder="Direction"
          value={direction}
          onChange={(v) => setDirection(v)}
          options={[
            { label: 'External', value: 'external' },
            { label: 'Internal', value: 'internal' },
          ]}
        />
        <Input.Search
          style={{ width: 240 }}
          placeholder="Search label/name"
          allowClear
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Space>
          <Typography.Text>Only active</Typography.Text>
          <Switch checked={onlyActive} onChange={setOnlyActive} />
        </Space>
      </Flex>

      <Tabs
        activeKey={activeTab}
        onChange={onTabChange}
        items={TABS.map((t) => ({ key: t.key, label: t.label }))}
      />

      {typesError && (
        <Alert
          type="error"
          title="Не удалось загрузить типы провайдеров"
          description="Проверьте доступность /api/providers/types и повторите попытку."
          showIcon
        />
      )}

      {isLoading || typesLoading ? (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      ) : isError ? (
        <Alert
          title="Failed to load providers"
          description="Please try again later."
          type="error"
          showIcon
        />
      ) : (
        <Card>
          <Table
            columns={columns}
            dataSource={providers as ResourceProvider[]}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="No providers configured" /> }}
          />
        </Card>
      )}

      {/* ── Modals ──────────────────────────────────────────────────────── */}
      <ProviderFormModal
        open={formOpen}
        provider={editingProvider}
        onClose={() => {
          setFormOpen(false);
          setEditingProvider(undefined);
        }}
      />
      <TestConnectionModal provider={testProvider} onClose={() => setTestProvider(undefined)} />
      <DeleteProviderModal provider={deleteProvider} onClose={() => setDeleteProvider(undefined)} />
      <CredentialAssignModal
        provider={credentialProvider}
        onClose={() => setCredentialProvider(undefined)}
      />
      <ShareProviderModal provider={shareProvider} onClose={() => setShareProvider(undefined)} />
      <ProviderUsageModal provider={usageProvider} onClose={() => setUsageProvider(undefined)} />
    </Flex>
  );
}

// Lightweight usage panel extracted inline for testability.
function ProviderUsageModal({
  provider,
  onClose,
}: {
  provider?: ResourceProvider;
  onClose: () => void;
}) {
  const { data, isLoading } = useGetProviderUsageQuery(provider?.id ?? 0, {
    skip: !provider,
  });
  return (
    <Modal open={!!provider} onCancel={onClose} onOk={onClose} title="Provider usage" footer={null}>
      {isLoading ? (
        <Flex justify="center" style={{ padding: '24px 0' }}>
          <Spin />
        </Flex>
      ) : data ? (
        <Flex vertical gap={8}>
          {(data.usage ?? []).map((item) => (
            <Flex key={item.resource} justify="space-between">
              <Typography.Text>{item.resource}</Typography.Text>
              <Typography.Text strong>{item.count}</Typography.Text>
            </Flex>
          ))}
        </Flex>
      ) : (
        <Empty description="No usage data" />
      )}
    </Modal>
  );
}

export default ProvidersPage;
