/**
 * @file index.tsx
 * @description Страница списка Docker Images: таблица с columns/dataSource, модальное окно добавления
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Spin,
  Modal,
  Input,
  App,
  Tooltip,
  Space,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  useListDockerImagesQuery,
  useCreateDockerImageMutation,
} from '../../store/api';
import { DockerImageSource } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function DockerImagesPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { data: sources = [], isLoading } = useListDockerImagesQuery();
  const [createSource] = useCreateDockerImageMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({
    name: '',
    registry_url: '',
    description: '',
    image_name: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      await createSource({
        name: form.name,
        registry_url: form.registry_url,
        description: form.description || undefined,
        image_name: form.image_name || undefined,
      }).unwrap();
      message.success('Docker registry added successfully');
      setDialogOpen(false);
      setForm({ name: '', registry_url: '', description: '', image_name: '' });
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenDialog = () => {
    setForm({ name: '', registry_url: '', description: '', image_name: '' });
    setDialogOpen(true);
  };

  const columns: ColumnsType<DockerImageSource> = [
    {
      title: 'Name',
      key: 'name',
      render: (_: unknown, record: DockerImageSource) => (
        <Flex vertical>
          <Typography.Text strong>{record.name}</Typography.Text>
          {record.description && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {record.description}
            </Typography.Text>
          )}
        </Flex>
      ),
    },
    {
      title: 'Registry URL',
      dataIndex: 'registry_url',
      key: 'registry_url',
      render: (val: string) => (
        <Typography.Text code style={{ fontSize: '0.8rem' }}>
          {val}
        </Typography.Text>
      ),
    },
    {
      title: 'Last Synced',
      dataIndex: 'last_synced_at',
      key: 'last_synced_at',
      render: (val: string | null) =>
        val ? new Date(val).toLocaleString() : '—',
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: DockerImageSource) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: DockerImageSource) => (
        <Tooltip title="Go to details">
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/docker-images/${record.id}`);
            }}
          />
        </Tooltip>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Docker Images
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenDialog}>
          Add Registry
        </Button>
      </Flex>

      {/* ── Table ───────────────────────────────────────────────────────────── */}
      <Card>
        <Table
          columns={columns}
          dataSource={sources as DockerImageSource[]}
          rowKey="id"
          loading={isLoading}
          onRow={(record) => ({
            onClick: () => navigate(`/docker-images/${record.id}`),
            style: { cursor: 'pointer' },
          })}
          pagination={false}
          locale={{ emptyText: 'No Docker image sources yet. Add a registry to get started.' }}
        />
      </Card>

      {/* ── Create Modal ────────────────────────────────────────────────────── */}
      <Modal
        title="Add Docker Registry"
        open={dialogOpen}
        onOk={handleCreate}
        onCancel={() => setDialogOpen(false)}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !form.name || !form.registry_url }}
        okText="Add"
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="Name (e.g. Docker Hub)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <Input
            placeholder="Registry URL (e.g. https://registry-1.docker.io)"
            value={form.registry_url}
            onChange={(e) => setForm({ ...form, registry_url: e.target.value })}
            required
          />
          <Input
            placeholder="Image Name — optional (e.g. library/nginx)"
            value={form.image_name}
            onChange={(e) => setForm({ ...form, image_name: e.target.value })}
          />
          <Input
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Space>
      </Modal>
    </Flex>
  );
}
