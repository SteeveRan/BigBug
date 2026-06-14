/**
 * @file GroupsTab.tsx
 * @description Вкладка Groups — таблица Source Groups + Import + Refresh + Delete
 * @dependencies antd, @ant-design/icons, RTK Query, PermissionGate
 */

import { useState, useMemo } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Space,
  Select,
  App,
  Tooltip,
  Spin,
  Alert,
  Empty,
  Badge,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ImportOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons';
import {
  useGetSourceProvidersQuery,
  useGetSourceGroupsQuery,
  useRefreshSourceGroupMutation,
  useDeleteSourceGroupMutation,
} from '../../../store/api';
import type { SourceGroup } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';
import { ImportGroupModal } from '../Groups/ImportGroupModal';

export function GroupsTab() {
  const { message } = App.useApp();

  const [selectedProviderId, setSelectedProviderId] = useState<number | undefined>(undefined);
  const [search] = useState('');
  const [importModalOpen, setImportModalOpen] = useState(false);

  // Fetch providers
  const {
    data: providers = [],
    isLoading: providersLoading,
    isError: providersError,
  } = useGetSourceProvidersQuery();

  // Auto-select first provider
  const effectiveProviderId = useMemo(() => {
    if (selectedProviderId != null) return selectedProviderId;
    if (providers.length > 0) return providers[0].id;
    return undefined;
  }, [selectedProviderId, providers]);

  // Fetch groups for selected provider
  const {
    data: groups = [],
    isLoading: groupsLoading,
    isError: groupsError,
  } = useGetSourceGroupsQuery(effectiveProviderId, {
    skip: effectiveProviderId == null,
  });

  const [refreshGroup] = useRefreshSourceGroupMutation();
  const [deleteGroup] = useDeleteSourceGroupMutation();

  // Filter by search
  const filteredGroups = useMemo(() => {
    if (!search.trim()) return groups;
    const term = search.toLowerCase();
    return groups.filter(
      (g) => g.name.toLowerCase().includes(term) || g.full_name.toLowerCase().includes(term)
    );
  }, [groups, search]);

  const handleRefresh = async (id: number) => {
    try {
      await refreshGroup(id).unwrap();
      message.success('Group refreshed');
    } catch {
      message.error('Failed to refresh group');
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete group "${name}"?`)) return;
    try {
      await deleteGroup(id).unwrap();
      message.success('Group deleted');
    } catch {
      message.error('Failed to delete group');
    }
  };

  const columns: ColumnsType<SourceGroup> = [
    {
      title: 'Name',
      key: 'name',
      render: (_: unknown, record: SourceGroup) => (
        <Flex vertical>
          <Typography.Text strong>{record.name}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.full_name}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Repositories',
      key: 'repositories',
      render: (_: unknown, record: SourceGroup) => (
        <Space size={8}>
          <Badge
            count={record.repositories_total}
            showZero
            style={{ backgroundColor: '#1677ff' }}
            overflowCount={999}
          >
            <span style={{ width: 0 }} />
          </Badge>
          <Typography.Text type="secondary">total</Typography.Text>
          <Badge
            count={record.repositories_mirrored}
            showZero
            style={{ backgroundColor: '#52c41a' }}
            overflowCount={999}
          >
            <span style={{ width: 0 }} />
          </Badge>
          <Typography.Text type="secondary">mirrored</Typography.Text>
        </Space>
      ),
    },
    {
      title: 'New Repos',
      key: 'new_repos',
      render: (_: unknown, record: SourceGroup) =>
        record.new_repos_count != null && record.new_repos_count > 0 ? (
          <Badge count={record.new_repos_count} style={{ backgroundColor: '#faad14' }} />
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 180,
      render: (_: unknown, record: SourceGroup) => (
        <Space size={4}>
          <PermissionGate permission="source_groups:write">
            <Tooltip title="Refresh">
              <Button
                size="small"
                type="text"
                icon={<ReloadOutlined />}
                onClick={() => handleRefresh(record.id)}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="source_groups:write">
            <Tooltip title="Delete">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(record.id, record.name)}
              />
            </Tooltip>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Text type="secondary">
          Source groups represent GitHub organizations or GitLab groups imported from a source
          provider. Import a group to auto-discover its repositories.
        </Typography.Text>
        <Space>
          <PermissionGate permission="source_groups:write">
            <Button
              type="primary"
              icon={<ImportOutlined />}
              onClick={() => setImportModalOpen(true)}
            >
              Import Group
            </Button>
          </PermissionGate>
        </Space>
      </Flex>

      {/* ── Provider Selector ───────────────────────────────────────────────── */}
      <Card size="small">
        <Flex gap={12} wrap="wrap">
          <div>
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: 'block', marginBottom: 4 }}
            >
              Source Provider
            </Typography.Text>
            {providersLoading ? (
              <Spin size="small" />
            ) : (
              <Select
                style={{ minWidth: 250 }}
                placeholder="All providers"
                value={effectiveProviderId}
                allowClear
                onChange={(v) => setSelectedProviderId(v)}
                options={[
                  { label: 'All Providers', value: 0 },
                  ...providers.map((p) => ({
                    label: `${p.label} (${p.provider_type})${p.is_anon ? ' [Anon]' : ''}${p.is_builtin ? ' [Builtin]' : ''}`,
                    value: p.id,
                  })),
                ]}
              />
            )}
          </div>
        </Flex>
      </Card>

      {/* ── Content ─────────────────────────────────────────────────────────── */}
      {providersError && (
        <Alert
          title="Failed to load providers"
          description="Please try again later."
          type="error"
          showIcon
        />
      )}

      {(groupsLoading || providersLoading) && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      )}

      {groupsError && (
        <Alert
          title="Failed to load groups"
          description="Please try again later."
          type="error"
          showIcon
        />
      )}

      {!groupsLoading && !groupsError && effectiveProviderId == null && providers.length === 0 && (
        <Card>
          <Empty description="No providers configured. Add a source provider first." />
        </Card>
      )}

      {!groupsLoading && !groupsError && effectiveProviderId != null && (
        <Card>
          <Table
            columns={columns}
            dataSource={filteredGroups as SourceGroup[]}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: <Empty description="No groups found" /> }}
          />
        </Card>
      )}

      {/* ── Import Group Modal ──────────────────────────────────────────────── */}
      <ImportGroupModal open={importModalOpen} onClose={() => setImportModalOpen(false)} />
    </Flex>
  );
}

export default GroupsTab;
