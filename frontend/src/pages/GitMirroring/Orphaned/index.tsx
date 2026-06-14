/**
 * @file Orphaned/index.tsx
 * @description Страница Orphaned Mirrors — таблица с поиском, фильтрами и модальным окном Re-link
 * @dependencies antd, @ant-design/icons, RTK Query, PermissionGate
 */

import { useState } from 'react';
import { Link } from 'react-router';
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
  Tag,
  Modal,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  DeleteOutlined,
  LinkOutlined,
  SwapOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import {
  useGetOrphanedMirrorsQuery,
  useDeleteOrphanedMirrorMutation,
  useGetGitlabInstancesQuery,
} from '../../../store/api';
import type { OrphanedMirror, OrphanReason, GitlabInstance } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';
import { RelinkModal } from './RelinkModal';

const ORPHAN_REASON_COLORS: Record<OrphanReason, string> = {
  provider_deleted: 'red',
  credentials_invalid: 'orange',
  source_not_found: 'yellow',
  target_manual_delete: 'magenta',
};

const ORPHAN_REASON_LABELS: Record<OrphanReason, string> = {
  provider_deleted: 'Provider Deleted',
  credentials_invalid: 'Credentials Invalid',
  source_not_found: 'Source Not Found',
  target_manual_delete: 'Target Deleted',
};

const PAGE_SIZE_OPTIONS = ['10', '20', '50'];

const OrphanedPage = () => {
  const { message } = App.useApp();

  // Filters & search
  const [search, setSearch] = useState('');
  const [gitlabInstanceFilter, setGitlabInstanceFilter] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Modal state
  const [relinkMirror, setRelinkMirror] = useState<OrphanedMirror | undefined>(undefined);
  const [relinkModalOpen, setRelinkModalOpen] = useState(false);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<OrphanedMirror | undefined>(undefined);

  const queryParams = {
    page,
    page_size: pageSize,
    ...(search.trim() ? { search: search.trim() } : {}),
    ...(gitlabInstanceFilter ? { gitlab_instance_id: gitlabInstanceFilter } : {}),
  };

  const { data, isLoading, isError } = useGetOrphanedMirrorsQuery(queryParams);
  const { data: gitlabInstances = [] } = useGetGitlabInstancesQuery();
  const [deleteOrphanedMirror, { isLoading: isDeleting }] = useDeleteOrphanedMirrorMutation();

  const orphanedMirrors = data?.items ?? [];
  const total = data?.total ?? 0;

  const handleDelete = async (mirror: OrphanedMirror) => {
    try {
      await deleteOrphanedMirror(mirror.mirror_id).unwrap();
      message.success(`Mirror "${mirror.mirror_name}" deleted`);
      setDeleteTarget(undefined);
    } catch {
      message.error('Failed to delete orphaned mirror');
    }
  };

  const handleOpenRelink = (mirror: OrphanedMirror, _tab?: 'reassign' | 'move-target' | 'delete') => {
    setRelinkMirror(mirror);
    setRelinkModalOpen(true);
    // tab selection is handled inside RelinkModal via initialTab prop if needed
  };

  const gitlabInstanceOptions = gitlabInstances.map((inst: GitlabInstance) => ({
    label: inst.name,
    value: inst.id,
  }));

  const columns: ColumnsType<OrphanedMirror> = [
    {
      title: 'Mirror Name',
      key: 'mirror_name',
      render: (_: unknown, record: OrphanedMirror) => (
        <Flex vertical>
          <Typography.Text strong style={{ cursor: 'pointer' }} onClick={() => handleOpenRelink(record)}>
            {record.mirror_name}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
            ID: {record.mirror_id}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Source URL',
      key: 'source_url',
      ellipsis: true,
      render: (_: unknown, record: OrphanedMirror) => (
        <Tooltip title={record.source_url}>
          <Typography.Text copyable style={{ fontSize: 13 }}>
            {record.source_url.length > 40
              ? `${record.source_url.substring(0, 40)}…`
              : record.source_url}
          </Typography.Text>
        </Tooltip>
      ),
    },
    {
      title: 'Target Path',
      key: 'target_path',
      render: (_: unknown, record: OrphanedMirror) => (
        <Typography.Text code>{record.target_path}</Typography.Text>
      ),
    },
    {
      title: 'Sync Group',
      key: 'sync_group_name',
      render: (_: unknown, record: OrphanedMirror) => (
        <Typography.Text>{record.sync_group_name ?? '—'}</Typography.Text>
      ),
    },
    {
      title: 'GitLab Instance',
      key: 'gitlab_instance_url',
      ellipsis: true,
      render: (_: unknown, record: OrphanedMirror) => (
        <Tooltip title={record.gitlab_instance_url}>
          <Typography.Text style={{ fontSize: 13 }}>
            {record.gitlab_instance_url.length > 30
              ? `${record.gitlab_instance_url.substring(0, 30)}…`
              : record.gitlab_instance_url}
          </Typography.Text>
        </Tooltip>
      ),
    },
    {
      title: 'Orphan Reason',
      key: 'orphan_reason',
      render: (_: unknown, record: OrphanedMirror) => (
        <Tooltip title={record.orphan_reason_text}>
          <Tag color={ORPHAN_REASON_COLORS[record.orphan_reason]}>
            {ORPHAN_REASON_LABELS[record.orphan_reason]}
          </Tag>
        </Tooltip>
      ),
    },
    {
      title: 'Detected At',
      key: 'detected_at',
      render: (_: unknown, record: OrphanedMirror) =>
        new Date(record.detected_at).toLocaleString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 200,
      render: (_: unknown, record: OrphanedMirror) => (
        <Space size={4}>
          <PermissionGate permission="mirrors:write">
            <Tooltip title="Reassign to Sync Group">
              <Button
                size="small"
                type="text"
                icon={<LinkOutlined />}
                onClick={() => handleOpenRelink(record)}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="mirrors:write">
            <Tooltip title="Move Target Path">
              <Button
                size="small"
                type="text"
                icon={<SwapOutlined />}
                onClick={() => handleOpenRelink(record)}
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
                onClick={() => setDeleteTarget(record)}
              />
            </Tooltip>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  if (isLoading) {
    return (
      <Card>
        <Flex justify="center" style={{ padding: 48 }}>
          <Spin size="large" />
        </Flex>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <Alert
          type="error"
          message="Failed to load orphaned mirrors"
          description="Could not retrieve the list of orphaned mirrors. Please try again."
          showIcon
        />
      </Card>
    );
  }

  return (
    <Flex vertical gap={16}>
      <Breadcrumb
        items={[
          { title: <Link to="/git-mirroring/dashboard">Git Mirroring</Link> },
          { title: 'Orphaned Mirrors' },
        ]}
      />
      <Card>
        <Flex vertical gap={16}>
          {/* Header */}
          <Flex justify="space-between" align="center" wrap gap={8}>
            <Flex vertical>
              <Typography.Title level={4} style={{ margin: 0 }}>
                Orphaned Mirrors
              </Typography.Title>
              <Typography.Text type="secondary">
                Mirrors that have lost connection to their source or target
              </Typography.Text>
            </Flex>
        </Flex>

        {/* Toolbar */}
        <Flex gap={12} wrap>
          <Input.Search
            placeholder="Search by name or URL…"
            allowClear
            style={{ maxWidth: 320 }}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
          <Select
            placeholder="GitLab Instance"
            allowClear
            style={{ minWidth: 200 }}
            value={gitlabInstanceFilter}
            onChange={(v) => {
              setGitlabInstanceFilter(v);
              setPage(1);
            }}
            options={gitlabInstanceOptions}
          />
          <Tooltip title="Refresh list">
            <Button icon={<SearchOutlined />} onClick={() => {}} disabled>
              Detect Orphaned
            </Button>
          </Tooltip>
        </Flex>

        {/* Table */}
        {orphanedMirrors.length === 0 ? (
          <Empty
            description="No orphaned mirrors found — all mirrors are properly connected"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <Table<OrphanedMirror>
            rowKey="mirror_id"
            columns={columns}
            dataSource={orphanedMirrors}
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: true,
              pageSizeOptions: PAGE_SIZE_OPTIONS,
              onChange: (p, ps) => {
                setPage(p);
                setPageSize(ps);
              },
            }}
            loading={isLoading}
            size="middle"
          />
        )}
      </Flex>

      {/* Relink Modal */}
      {relinkMirror && (
        <RelinkModal
          mirror={relinkMirror}
          open={relinkModalOpen}
          onClose={() => {
            setRelinkModalOpen(false);
            setRelinkMirror(undefined);
          }}
        />
      )}

      {/* Delete Confirmation */}
      <Modal
        title="Delete Orphaned Mirror"
        open={!!deleteTarget}
        onOk={() => deleteTarget && handleDelete(deleteTarget)}
        onCancel={() => setDeleteTarget(undefined)}
        okText="Delete"
        okButtonProps={{ danger: true, loading: isDeleting }}
        cancelText="Cancel"
      >
        <Alert
          type="warning"
          title="This will soft-delete the mirror. It can be restored within 30 days."
          showIcon
          style={{ marginBottom: 16 }}
        />
        {deleteTarget && (
          <Typography.Text>
            Are you sure you want to delete mirror <strong>"{deleteTarget.mirror_name}"</strong>?
          </Typography.Text>
        )}
      </Modal>
    </Card>
  </Flex>
  );
};

export default OrphanedPage;
