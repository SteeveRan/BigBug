/**
 * @file index.tsx
 * @description Страница списка Helm Charts: таблица с columns/dataSource, модальное окно добавления
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Card, Typography, Button, Table, Flex, Modal, Input, App, Tooltip, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  useListHelmChartsQuery,
  useCreateHelmChartMutation,
  useIndexHelmChartMutation,
} from '../../store/api';
import { HelmChartSource } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function HelmChartsPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { data: charts = [], isLoading } = useListHelmChartsQuery();
  const [createChart] = useCreateHelmChartMutation();
  const [indexChart] = useIndexHelmChartMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ name: '', repo_url: '', description: '' });
  const [submitting, setSubmitting] = useState(false);

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      await createChart(form).unwrap();
      message.success('Helm chart source added successfully');
      setDialogOpen(false);
      setForm({ name: '', repo_url: '', description: '' });
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenDialog = () => {
    setForm({ name: '', repo_url: '', description: '' });
    setDialogOpen(true);
  };

  const columns: ColumnsType<HelmChartSource> = [
    {
      title: 'Name',
      key: 'name',
      render: (_: unknown, record: HelmChartSource) => (
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
      title: 'Repository URL',
      dataIndex: 'repo_url',
      key: 'repo_url',
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
      render: (val: string | null) => (val ? new Date(val).toLocaleString() : '—'),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: HelmChartSource) => (
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
      render: (_: unknown, record: HelmChartSource) => (
        <Tooltip title="Re-index now">
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              indexChart(record.id);
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
          Helm Charts
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenDialog}>
          Add Chart Source
        </Button>
      </Flex>

      {/* ── Table ───────────────────────────────────────────────────────────── */}
      <Card>
        <Table
          columns={columns}
          dataSource={charts as HelmChartSource[]}
          rowKey="id"
          loading={isLoading}
          onRow={(record) => ({
            onClick: () => navigate(`/helm-charts/${record.id}`),
            style: { cursor: 'pointer' },
          })}
          pagination={false}
          locale={{ emptyText: 'No Helm chart sources yet. Add one to get started.' }}
        />
      </Card>

      {/* ── Create Modal ────────────────────────────────────────────────────── */}
      <Modal
        title="Add Helm Chart Source"
        open={dialogOpen}
        onOk={handleCreate}
        onCancel={() => setDialogOpen(false)}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !form.name || !form.repo_url }}
        okText="Add"
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="Name (e.g. stable)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <Input
            placeholder="Repository URL (e.g. https://charts.helm.sh/stable)"
            value={form.repo_url}
            onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
            required
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
