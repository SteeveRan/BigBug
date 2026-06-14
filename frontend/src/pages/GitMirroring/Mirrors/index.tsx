/**
 * @file Mirrors/index.tsx
 * @description Страница списка зеркал Git Mirroring — таблица, search bar, фильтры, actions (Group F)
 * @dependencies antd, @ant-design/icons, RTK Query, PermissionGate, StatusChip
 */

import { useState } from 'react';
import { useNavigate, Link } from 'react-router';
import {
  Breadcrumb,
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Space,
  Input,
  Select,
  App,
  Tooltip,
  Spin,
  Alert,
  Empty,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  ImportOutlined,
  SyncOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  EditOutlined,
} from '@ant-design/icons';
import {
  useGetMirrorsQuery,
  useDeleteMirrorV2Mutation,
  useTriggerMirrorSyncMutation,
  useTriggerFreshnessCheckMutation,
} from '../../../store/api';
import type { Mirror, MirrorFilters } from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';
import { CreateMirrorModal } from './CreateMirrorModal';
import { ImportMirrorModal } from './ImportMirrorModal';

const STATUS_OPTIONS = [
  { label: 'All', value: -1 },
  { label: 'OK', value: 0 },
  { label: 'Failed', value: 1 },
  { label: 'Warning', value: 2 },
  { label: 'In Progress', value: 3 },
  { label: 'Pending', value: 4 },
];

const PAGE_SIZE_OPTIONS = ['10', '20', '50'];

const MirrorsPage = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();

  // Filters & search
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<number>(-1);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Modal state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editMirror, setEditMirror] = useState<Mirror | undefined>(undefined);
  const [importModalOpen, setImportModalOpen] = useState(false);

  // Build query params
  const queryParams: MirrorFilters = {
    limit: pageSize,
    offset: (page - 1) * pageSize,
  };
  if (statusFilter !== -1) queryParams.status_flag = statusFilter;
  if (search.trim()) queryParams.search = search.trim();

  const { data: mirrors = [], isLoading, isError } = useGetMirrorsQuery(queryParams);
  const [deleteMirror] = useDeleteMirrorV2Mutation();
  const [triggerSync] = useTriggerMirrorSyncMutation();
  const [triggerFreshness] = useTriggerFreshnessCheckMutation();

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete mirror for "${name}"?`)) return;
    try {
      await deleteMirror(id).unwrap();
      message.success('Mirror deleted');
    } catch {
      message.error('Failed to delete mirror');
    }
  };

  const handleSync = async (id: number) => {
    try {
      await triggerSync(id).unwrap();
      message.success('Sync triggered');
    } catch {
      // error handled by RTK Query
    }
  };

  const handleFreshness = async (id: number) => {
    try {
      await triggerFreshness(id).unwrap();
      message.success('Freshness check triggered');
    } catch {
      // error handled by RTK Query
    }
  };

  const columns: ColumnsType<Mirror> = [
    {
      title: 'Source Repository',
      key: 'source_repository',
      render: (_: unknown, record: Mirror) => (
        <Flex vertical>
          <Typography.Text strong>
            {record.source_repository?.full_name ?? record.source_repository_id}
          </Typography.Text>
          {record.source_repository?.description && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
              {record.source_repository.description}
            </Typography.Text>
          )}
        </Flex>
      ),
    },
    {
      title: 'Target GitLab',
      key: 'target',
      render: (_: unknown, record: Mirror) => (
        <Flex vertical>
          <Typography.Text>
            {record.target_gitlab_name ? `${record.target_gitlab_name}` : '—'}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.target_path}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: Mirror) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Sync Group',
      key: 'sync_group',
      render: (_: unknown, record: Mirror) => (
        <Typography.Text>{record.sync_group_name ?? record.sync_group_id}</Typography.Text>
      ),
    },
    {
      title: 'Last Sync',
      key: 'last_sync',
      render: (_: unknown, record: Mirror) =>
        record.last_sync_at ? new Date(record.last_sync_at).toLocaleString() : '—',
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 200,
      render: (_: unknown, record: Mirror) => (
        <Space size={4}>
          <PermissionGate permission="mirrors:sync">
            <Tooltip title="Trigger Sync">
              <Button
                size="small"
                type="text"
                icon={<SyncOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleSync(record.id);
                }}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="mirrors:sync">
            <Tooltip title="Freshness Check">
              <Button
                size="small"
                type="text"
                icon={<CheckCircleOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleFreshness(record.id);
                }}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="mirrors:write">
            <Tooltip title="Edit">
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  setEditMirror(record);
                  setCreateModalOpen(true);
                }}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="mirrors:delete">
            <Tooltip title="Delete">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(
                    record.id,
                    record.source_repository?.full_name ?? String(record.source_repository_id)
                  );
                }}
              />
            </Tooltip>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Breadcrumb ──────────────────────────────────────────────────────── */}
      <Breadcrumb
        items={[
          { title: <Link to="/git-mirroring/dashboard">Git Mirroring</Link> },
          { title: 'Mirrors' },
        ]}
      />

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Flex vertical gap={4}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Mirrors
          </Typography.Title>
          <Typography.Text type="secondary">
            Manage mirrors — each mirror links a source repository to a target GitLab instance.
            Trigger sync or freshness checks and monitor mirror status.
          </Typography.Text>
        </Flex>
        <Space wrap>
          <PermissionGate permission="mirrors:write">
            <Button icon={<ImportOutlined />} onClick={() => setImportModalOpen(true)}>
              Import Existing Mirror
            </Button>
          </PermissionGate>
          <PermissionGate permission="mirrors:write">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditMirror(undefined);
                setCreateModalOpen(true);
              }}
            >
              Create Mirror
            </Button>
          </PermissionGate>
        </Space>
      </Flex>

      {/* ── Search & Filters ────────────────────────────────────────────────── */}
      <Card size="small">
        <Flex gap={12} wrap="wrap">
          <Input.Search
            placeholder="Search by source URL, org/repo, target GitLab, target path..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            onSearch={() => setPage(1)}
            style={{ flex: 1, minWidth: 300 }}
            allowClear
          />
          <Select
            style={{ width: 150 }}
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            options={STATUS_OPTIONS}
          />
        </Flex>
      </Card>

      {/* ── Content ─────────────────────────────────────────────────────────── */}
      {isLoading && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      )}

      {isError && (
        <Alert
          title="Failed to load mirrors"
          description="Please try again later."
          type="error"
          showIcon
        />
      )}

      {!isLoading && !isError && (
        <Card>
          <Table
            columns={columns}
            dataSource={mirrors as Mirror[]}
            rowKey="id"
            loading={isLoading}
            onRow={(record) => ({
              onClick: () => navigate(`/git-mirroring/mirrors/${record.id}`),
              style: { cursor: 'pointer' },
            })}
            pagination={{
              current: page,
              pageSize,
              showSizeChanger: true,
              pageSizeOptions: PAGE_SIZE_OPTIONS,
              onChange: (p, ps) => {
                setPage(p);
                setPageSize(ps);
              },
            }}
            locale={{ emptyText: <Empty description="No mirrors found" /> }}
          />
        </Card>
      )}

      {/* ── Create/Edit Mirror Modal ────────────────────────────────────────── */}
      <CreateMirrorModal
        open={createModalOpen}
        onClose={() => {
          setCreateModalOpen(false);
          setEditMirror(undefined);
        }}
        mirror={editMirror}
      />

      {/* ── Import Mirror Modal ─────────────────────────────────────────────── */}
      <ImportMirrorModal open={importModalOpen} onClose={() => setImportModalOpen(false)} />
    </Flex>
  );
};

export default MirrorsPage;
