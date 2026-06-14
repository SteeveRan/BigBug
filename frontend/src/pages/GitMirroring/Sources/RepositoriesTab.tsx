/**
 * @file RepositoriesTab.tsx
 * @description Вкладка Repositories — таблица source репозиториев + Add + Bulk Create + фильтры
 * @dependencies antd, react-router, RTK Query, PermissionGate
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Table,
  Flex,
  Space,
  Input,
  Select,
  Spin,
  Alert,
  Empty,
  Tag,
  Tooltip,
  Button,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { EyeOutlined, PlusOutlined, ThunderboltOutlined, DeleteOutlined } from '@ant-design/icons';
import {
  useGetSourceProvidersQuery,
  useGetSourceGroupsQuery,
  useGetSourceRepositoriesQuery,
  useDeleteSourceRepositoryMutation,
} from '../../../store/api';
import type { SourceRepository } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';
import { AddRepositoryModal } from './AddRepositoryModal';
import { BulkCreateMirrorsModal } from './BulkCreateMirrorsModal';

const DISCOVERY_STATUS_OPTIONS = [
  { label: 'All', value: -1 },
  { label: 'OK', value: 0 },
  { label: 'Failed', value: 1 },
  { label: 'Warning', value: 2 },
  { label: 'In Progress', value: 3 },
  { label: 'Pending', value: 4 },
];

export function RepositoriesTab() {
  const navigate = useNavigate();

  // Provider → Group selection
  const { data: providers = [], isLoading: providersLoading } = useGetSourceProvidersQuery();

  const [selectedProviderId, setSelectedProviderId] = useState<number | undefined>(undefined);
  const [search, setSearch] = useState('');
  const [discoveryFilter, setDiscoveryFilter] = useState<number>(-1);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [bulkModalOpen, setBulkModalOpen] = useState(false);

  // Auto-select first provider
  const effectiveProviderId = useMemo(() => {
    if (selectedProviderId != null) return selectedProviderId;
    if (providers.length > 0) return providers[0].id;
    return undefined;
  }, [selectedProviderId, providers]);

  // Fetch groups for selected provider
  const { data: groups = [], isLoading: groupsLoading } = useGetSourceGroupsQuery(
    effectiveProviderId ?? 0,
    { skip: effectiveProviderId == null }
  );

  // Auto-select first group for modals (preselection), fall back to 0
  // when no groups exist yet.
  const effectiveGroupId = useMemo(() => {
    if (groups.length > 0) return groups[0].id;
    return 0;
  }, [groups]);

  // Fetch repositories — always use group_id=0 (All Groups) since there's no group filter.
  const {
    data: repositories = [],
    isLoading: reposLoading,
    isError: reposError,
  } = useGetSourceRepositoriesQuery(
    {
      group_id: 0,
      discovery_status: discoveryFilter !== -1 ? discoveryFilter : undefined,
      search: search.trim() || undefined,
      is_archived: false,
    },
  );

  const [deleteRepo] = useDeleteSourceRepositoryMutation();

  const handleDelete = async (id: number, fullName: string) => {
    if (!window.confirm(`Delete repository "${fullName}"?`)) return;
    try {
      await deleteRepo(id).unwrap();
      message.success('Repository deleted');
    } catch {
      message.error('Failed to delete repository');
    }
  };

  const columns: ColumnsType<SourceRepository> = [
    {
      title: 'Repository',
      key: 'name',
      render: (_: unknown, record: SourceRepository) => (
        <Flex vertical>
          <Typography.Text strong>{record.full_name}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.name}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Description',
      key: 'description',
      render: (_: unknown, record: SourceRepository) => (
        <Typography.Text type="secondary" ellipsis={{ tooltip: true }} style={{ maxWidth: 300 }}>
          {record.description || '—'}
        </Typography.Text>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: SourceRepository) => (
        <Space size={4}>
          {record.is_archived && <Tag color="warning">Archived</Tag>}
          {record.is_fork && <Tag color="processing">Fork</Tag>}
          {record.is_private && <Tag>Private</Tag>}
          {record.is_disabled && <Tag color="red">Disabled</Tag>}
        </Space>
      ),
    },
    {
      title: 'Language',
      key: 'language',
      width: 100,
      render: (_: unknown, record: SourceRepository) => (
        <Typography.Text>{record.language || '—'}</Typography.Text>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 120,
      render: (_: unknown, record: SourceRepository) => (
        <Space size={4}>
          <Tooltip title="View Details">
            <EyeOutlined
              style={{ cursor: 'pointer', fontSize: 16, color: '#1677ff' }}
              onClick={() => navigate(`/git-mirroring/repositories/${record.id}`)}
            />
          </Tooltip>
          <PermissionGate permission="source_groups:write">
            <Tooltip title="Delete">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(record.id, record.full_name)}
              />
            </Tooltip>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  const isLoading = providersLoading || groupsLoading || reposLoading;

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Text type="secondary">
          Source repositories discovered from imported groups or added manually for Generic Git
          providers.
        </Typography.Text>
        <Space>
          <PermissionGate permission="source_groups:write">
            <Button
              icon={<PlusOutlined />}
              onClick={() => setAddModalOpen(true)}
            >
              Add Repository
            </Button>
          </PermissionGate>
          <PermissionGate permission="mirrors:write">
            <Button
              icon={<ThunderboltOutlined />}
              onClick={() => setBulkModalOpen(true)}
              disabled={repositories.length === 0}
            >
              Bulk Create Mirrors
            </Button>
          </PermissionGate>
        </Space>
      </Flex>

      {/* ── Filters ─────────────────────────────────────────────────────────── */}
      <Card size="small">
        <Flex gap={12} wrap="wrap">
          <div>
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: 'block', marginBottom: 4 }}
            >
              Source Provider
            </Typography.Text>
            <Select
              style={{ minWidth: 220 }}
              placeholder="All providers"
              value={effectiveProviderId}
              allowClear
              onChange={(v) => setSelectedProviderId(v)}
              loading={providersLoading}
              options={providers.map((p) => ({
                label: `${p.label} (${p.provider_type})`,
                value: p.id,
              }))}
            />
          </div>
          <div>
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: 'block', marginBottom: 4 }}
            >
              Search
            </Typography.Text>
            <Input.Search
              placeholder="Search repositories..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ minWidth: 200 }}
              allowClear
            />
          </div>
          <div>
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: 'block', marginBottom: 4 }}
            >
              Status
            </Typography.Text>
            <Select
              style={{ width: 140 }}
              value={discoveryFilter}
              onChange={(v) => setDiscoveryFilter(v)}
              options={DISCOVERY_STATUS_OPTIONS}
            />
          </div>
        </Flex>
      </Card>

      {/* ── Content ─────────────────────────────────────────────────────────── */}
      {isLoading && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      )}

      {reposError && (
        <Alert
          message="Failed to load repositories"
          description="Please select a valid group or try again later."
          type="error"
          showIcon
        />
      )}

      {!isLoading && !reposError && (
        <Card>
          <Table
            columns={columns}
            dataSource={repositories as SourceRepository[]}
            rowKey="id"
            onRow={(record) => ({
              onClick: () => navigate(`/git-mirroring/repositories/${record.id}`),
              style: { cursor: 'pointer' },
            })}
            pagination={{
              pageSize: 20,
              showSizeChanger: true,
              pageSizeOptions: ['10', '20', '50'],
            }}
            locale={{ emptyText: <Empty description="No repositories found" /> }}
          />
        </Card>
      )}

      {/* ── Modals ──────────────────────────────────────────────────────────── */}
      <AddRepositoryModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        preselectedProviderId={effectiveProviderId}
      />
      <BulkCreateMirrorsModal
        open={bulkModalOpen}
        onClose={() => setBulkModalOpen(false)}
        groupId={effectiveGroupId}
      />
    </Flex>
  );
}

export default RepositoriesTab;
