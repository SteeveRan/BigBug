/**
 * @file SyncGroups/Detail.tsx
 * @description Страница детализации Sync Group — cron расписания, concurrency, pipeline, mirrors count + таблица зеркал
 * @dependencies antd, react-router, RTK Query, StatusChip
 */

import { useParams, useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Descriptions,
  Table,
  Tag,
  Button,
  Flex,
  Space,
  Spin,
  Alert,
  Empty,
  Breadcrumb,
  Switch,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ArrowLeftOutlined } from '@ant-design/icons';
import {
  useGetSyncGroupQuery,
  useGetMirrorsQuery,
} from '../../../store/api';
import type { Mirror } from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';

const SyncGroupDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const groupId = Number(id);

  const {
    data: syncGroup,
    isLoading: groupLoading,
    isError: groupError,
  } = useGetSyncGroupQuery(groupId, { skip: isNaN(groupId) });

  const {
    data: mirrors = [],
    isLoading: mirrorsLoading,
  } = useGetMirrorsQuery({ sync_group_id: groupId }, { skip: isNaN(groupId) });

  const mirrorColumns: ColumnsType<Mirror> = [
    {
      title: 'Source URL',
      dataIndex: 'source_url',
      key: 'source_url',
      ellipsis: true,
      render: (_: unknown, record: Mirror) => (
        <Typography.Text>
          {record.source_repository?.web_url || record.target_path}
        </Typography.Text>
      ),
    },
    {
      title: 'Target Path',
      dataIndex: 'target_path',
      key: 'target_path',
      ellipsis: true,
      render: (path: string) => (
        <Typography.Text code>{path}</Typography.Text>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status_flag',
      key: 'status_flag',
      width: 140,
      render: (flag: number, record: Mirror) => (
        <StatusChip statusFlag={flag} statusText={record.status_text} />
      ),
    },
    {
      title: 'Last Sync',
      dataIndex: 'last_sync_at',
      key: 'last_sync_at',
      width: 180,
      render: (date: string | undefined) =>
        date ? (
          <Typography.Text>{new Date(date).toLocaleString()}</Typography.Text>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
  ];

  if (isNaN(groupId)) {
    return (
      <Flex vertical gap={16}>
        <Alert title="Invalid Sync Group ID" type="error" showIcon />
        <Button onClick={() => navigate('/git-mirroring/sync-groups')}>Back to Sync Groups</Button>
      </Flex>
    );
  }

  if (groupLoading) {
    return (
      <Flex justify="center" style={{ padding: '40px 0' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  if (groupError || !syncGroup) {
    return (
      <Flex vertical gap={16}>
        <Alert
          message="Failed to load Sync Group"
          description="The sync group may have been deleted or you may not have permission to view it."
          type="error"
          showIcon
        />
        <Button onClick={() => navigate('/git-mirroring/sync-groups')}>Back to Sync Groups</Button>
      </Flex>
    );
  }

  return (
    <Flex vertical gap={16}>
      {/* ── Breadcrumb ────────────────────────────────────────────────────── */}
      <Breadcrumb
        items={[
          { title: <Typography.Link onClick={() => navigate('/git-mirroring/sync-groups')}>Sync Groups</Typography.Link> },
          { title: syncGroup.name },
        ]}
      />

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/git-mirroring/sync-groups')}
          >
            Back
          </Button>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {syncGroup.name}
            {syncGroup.is_default && <Tag color="blue" style={{ marginLeft: 8 }}>Default</Tag>}
          </Typography.Title>
        </Space>
        <PermissionGate permission="sync_groups:write">
          <Button
            type="primary"
            onClick={() => navigate('/git-mirroring/sync-groups', { state: { editId: syncGroup.id } })}
          >
            Edit
          </Button>
        </PermissionGate>
      </Flex>

      {/* ── Details Card ──────────────────────────────────────────────────── */}
      <Card title="Configuration">
        <Descriptions bordered column={{ xs: 1, sm: 2 }}>
          <Descriptions.Item label="Description">
            {syncGroup.description || '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Pipeline">
            {syncGroup.pipeline?.name || (syncGroup.pipeline_id ? `ID: ${syncGroup.pipeline_id}` : '—')}
          </Descriptions.Item>
          <Descriptions.Item label="Mirrors Count">
            {syncGroup.mirrors_count ?? (mirrors.length > 0 ? mirrors.length : '—')}
          </Descriptions.Item>
          <Descriptions.Item label="Created">
            {new Date(syncGroup.created_at).toLocaleString()}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* ── Sync Configuration ────────────────────────────────────────────── */}
      <Card title="Sync Configuration">
        <Descriptions bordered column={{ xs: 1, sm: 2 }}>
          <Descriptions.Item label="Sync Enabled">
            <Switch checked={syncGroup.sync_enabled} disabled size="small" />
          </Descriptions.Item>
          <Descriptions.Item label="Sync Cron">
            <Typography.Text code>{syncGroup.sync_cron || '—'}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Sync Concurrency">
            {syncGroup.sync_concurrency}
          </Descriptions.Item>
          <Descriptions.Item label="Freshness Enabled">
            <Switch checked={syncGroup.freshness_enabled} disabled size="small" />
          </Descriptions.Item>
          <Descriptions.Item label="Freshness Cron">
            <Typography.Text code>{syncGroup.freshness_cron || '—'}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Freshness Concurrency">
            {syncGroup.freshness_concurrency}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* ── Mirrors Table ─────────────────────────────────────────────────── */}
      <Card title={`Mirrors (${mirrors.length})`}>
        {mirrorsLoading ? (
          <Flex justify="center" style={{ padding: '40px 0' }}>
            <Spin size="large" />
          </Flex>
        ) : (
          <Table
            columns={mirrorColumns}
            dataSource={mirrors}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: <Empty description="No mirrors assigned to this sync group" /> }}
          />
        )}
      </Card>
    </Flex>
  );
};

export default SyncGroupDetailPage;
