/**
 * @file DockerImageDetail.tsx
 * @description Страница деталей Docker Image: source info, теги, история синхронизации + модальное окно Index Image
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useParams, useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Spin,
  Divider,
  Modal,
  Input,
  App,
  Tooltip,
  Space,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import { useState } from 'react';
import {
  useGetDockerImageQuery,
  useGetDockerImageTagsQuery,
  useGetDockerImageLogsQuery,
  useIndexDockerImageMutation,
} from '../../store/api';
import { DockerImageSourceDetail, DockerImageTag, DockerSyncLog } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function DockerImageDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const sourceId = Number(id);

  const { data: source, isLoading } = useGetDockerImageQuery(sourceId);
  const { data: tags = [] } = useGetDockerImageTagsQuery(sourceId);
  const { data: logs = [] } = useGetDockerImageLogsQuery(sourceId);
  const [indexImage, { isLoading: indexing }] = useIndexDockerImageMutation();

  const [indexDialogOpen, setIndexDialogOpen] = useState(false);
  const [imageName, setImageName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const s = source as DockerImageSourceDetail | undefined;

  const handleIndex = async () => {
    setSubmitting(true);
    try {
      await indexImage({ id: sourceId, image_name: imageName }).unwrap();
      message.success(`Indexing started for ${imageName}`);
      setIndexDialogOpen(false);
      setImageName('');
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  const formatBytes = (bytes: number | null): string => {
    if (bytes === null) return '—';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIdx = 0;
    while (size >= 1024 && unitIdx < units.length - 1) {
      size /= 1024;
      unitIdx++;
    }
    return `${size.toFixed(1)} ${units[unitIdx]}`;
  };

  // ── Loading / Not Found ──────────────────────────────────────────────────
  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: 48 }}>
        <Spin size="large" />
      </Flex>
    );
  }
  if (!s) {
    return (
      <Flex vertical align="center" gap={16} style={{ padding: 48 }}>
        <Typography.Text type="secondary">Docker image source not found</Typography.Text>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/docker-images')}>
          Back to Docker Images
        </Button>
      </Flex>
    );
  }

  // ── Tags Table Columns ───────────────────────────────────────────────────
  const tagColumns: ColumnsType<DockerImageTag> = [
    {
      title: 'Image',
      key: 'image',
      render: (_: unknown, record: DockerImageTag) => (
        <Typography.Text strong code style={{ fontSize: '0.8rem' }}>
          {record.image_name}
        </Typography.Text>
      ),
    },
    {
      title: 'Tag',
      dataIndex: 'tag',
      key: 'tag',
      render: (val: string) => (
        <Typography.Text code style={{ fontSize: '0.8rem' }}>
          {val}
        </Typography.Text>
      ),
    },
    {
      title: 'Architecture',
      dataIndex: 'architectures',
      key: 'architectures',
      render: (val: string | null) =>
        val ? (
          <Typography.Text code style={{ fontSize: '0.8rem' }}>
            {val}
          </Typography.Text>
        ) : (
          '—'
        ),
    },
    {
      title: 'Size',
      key: 'size',
      render: (_: unknown, record: DockerImageTag) => formatBytes(record.size_bytes),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: DockerImageTag) => (
        <Flex align="center" gap={8}>
          <StatusChip
            statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
            statusText={record.status_text}
          />
          {record.is_synced && (
            <Typography.Text type="success" strong style={{ fontSize: 12 }}>
              ✓ Synced
            </Typography.Text>
          )}
        </Flex>
      ),
    },
  ];

  // ── Sync History Table Columns ───────────────────────────────────────────
  const logColumns: ColumnsType<DockerSyncLog> = [
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: 'Triggered By',
      dataIndex: 'triggered_by',
      key: 'triggered_by',
      render: (val: string | null) => val ?? '—',
    },
    {
      title: 'Pipeline',
      key: 'pipeline',
      render: (_: unknown, record: DockerSyncLog) =>
        record.pipeline_url ? (
          <Button
            size="small"
            type="link"
            icon={<LinkOutlined />}
            href={record.pipeline_url}
            target="_blank"
          >
            #{record.pipeline_id}
          </Button>
        ) : (
          (record.pipeline_id ?? '—')
        ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: DockerSyncLog) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: unknown, record: DockerSyncLog) => {
        if (record.started_at && record.finished_at) {
          const seconds = Math.round(
            (new Date(record.finished_at).getTime() - new Date(record.started_at).getTime()) / 1000,
          );
          return `${seconds}s`;
        }
        return '—';
      },
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex align="center" gap={12} wrap="wrap">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/docker-images')}>
          Back
        </Button>
        <Typography.Title level={4} style={{ margin: 0, flex: 1 }}>
          {s.name}
        </Typography.Title>
        <Tooltip title={indexing ? 'Indexing…' : 'Index image tags from registry'}>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={() => setIndexDialogOpen(true)}
            loading={indexing}
          >
            Index Image
          </Button>
        </Tooltip>
        <Button
          icon={<LinkOutlined />}
          href={s.registry_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open Registry
        </Button>
      </Flex>

      {/* ── Info + Tags Cards ───────────────────────────────────────────────── */}
      <Flex gap={16} wrap="wrap">
        {/* Source Info Card */}
        <Card title="Source Info" style={{ flex: '1 1 300px', minWidth: 280 }}>
          <Flex vertical gap={12}>
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Status
              </Typography.Text>
              <StatusChip
                statusFlag={s.status_flag as 0 | 1 | 2 | 3 | 4}
                statusText={s.status_text}
              />
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Registry URL
              </Typography.Text>
              <Typography.Text code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                {s.registry_url}
              </Typography.Text>
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Description
              </Typography.Text>
              <Typography.Text>{s.description ?? '—'}</Typography.Text>
            </Flex>
            <Divider style={{ margin: 0 }} />
            <Flex vertical>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Last Synced
              </Typography.Text>
              <Typography.Text>
                {s.last_synced_at
                  ? new Date(s.last_synced_at).toLocaleString()
                  : 'Never'}
              </Typography.Text>
            </Flex>
            {s.gitlab_project_url && (
              <>
                <Divider style={{ margin: 0 }} />
                <Flex vertical>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    GitLab Project
                  </Typography.Text>
                  <Typography.Link href={s.gitlab_project_url} target="_blank" rel="noopener noreferrer">
                    {s.gitlab_project_id ?? s.gitlab_project_url}
                  </Typography.Link>
                </Flex>
              </>
            )}
          </Flex>
        </Card>

        {/* Image Tags Card */}
        <Card
          title={`Image Tags (${(tags as DockerImageTag[]).length})`}
          style={{ flex: '2 1 500px', minWidth: 350 }}
        >
          <Table
            columns={tagColumns}
            dataSource={tags as DockerImageTag[]}
            rowKey="id"
            size="small"
            pagination={false}
            scroll={{ y: 360 }}
            locale={{
              emptyText: 'No tags indexed yet. Click "Index Image" to fetch tags.',
            }}
          />
        </Card>
      </Flex>

      {/* ── Sync History Card ───────────────────────────────────────────────── */}
      <Card title="Sync History">
        <Table
          columns={logColumns}
          dataSource={logs as DockerSyncLog[]}
          rowKey="id"
          size="small"
          pagination={false}
          locale={{ emptyText: 'No sync history yet' }}
        />
      </Card>

      {/* ── Index Image Modal ───────────────────────────────────────────────── */}
      <Modal
        title="Index Image Tags"
        open={indexDialogOpen}
        onOk={handleIndex}
        onCancel={() => setIndexDialogOpen(false)}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !imageName }}
        okText="Index"
        cancelText="Cancel"
      >
        <Input
          placeholder="Image Name (e.g. library/nginx)"
          value={imageName}
          onChange={(e) => setImageName(e.target.value)}
          required
        />
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Full image name to index (e.g., library/nginx, bitnami/postgresql)
        </Typography.Text>
      </Modal>
    </Flex>
  );
}
