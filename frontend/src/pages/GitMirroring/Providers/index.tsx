/**
 * @file Providers/index.tsx
 * @description Страница Source Providers — таблица с add, edit, test, delete (Group F)
 * @dependencies antd, @ant-design/icons, RTK Query, PermissionGate, StatusChip
 */

import { useState, useMemo } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Space,
  App,
  Tooltip,
  Spin,
  Alert,
  Empty,
  Tag,
  Select,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useGetSourceProvidersQuery, useDeleteSourceProviderMutation } from '../../../store/api';
import type { SourceProvider } from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';
import { ProviderModal } from './ProviderModal';

const PROVIDER_TYPE_OPTIONS = [
  { label: 'All', value: '' },
  { label: 'GitHub', value: 'github' },
  { label: 'GitLab', value: 'gitlab' },
  { label: 'Bitbucket', value: 'bitbucket' },
  { label: 'Generic Git', value: 'generic' },
];

const PROVIDER_TYPE_COLORS: Record<string, string> = {
  github: '#24292f',
  gitlab: '#fc6d26',
  bitbucket: '#0052cc',
  generic: '#8c8c8c',
};

const ProvidersPage = () => {
  const { message } = App.useApp();

  const { data: providers = [], isLoading, isError } = useGetSourceProvidersQuery();

  const [deleteProvider] = useDeleteSourceProviderMutation();
  const [modalOpen, setModalOpen] = useState(false);
  const [editProvider, setEditProvider] = useState<SourceProvider | undefined>(undefined);
  const [typeFilter, setTypeFilter] = useState<string>('');

  // Client-side filter by provider type
  const filteredProviders = useMemo(() => {
    if (!typeFilter) return providers;
    return providers.filter((p) => p.provider_type === typeFilter);
  }, [providers, typeFilter]);

  const handleDelete = async (id: number, label: string) => {
    if (!window.confirm(`Delete provider "${label}"?`)) return;
    try {
      await deleteProvider(id).unwrap();
      message.success('Provider deleted');
    } catch {
      message.error('Failed to delete provider');
    }
  };

  const handleTestConnection = async (id: number) => {
    try {
      // No dedicated test hook, just show a message
      message.info(`Connection test for provider #${id} not yet implemented on backend`);
    } catch {
      message.error('Connection test failed');
    }
  };

  const columns: ColumnsType<SourceProvider> = [
    {
      title: 'Label',
      dataIndex: 'label',
      key: 'label',
      render: (label: string, record: SourceProvider) => (
        <Flex vertical>
          <Typography.Text strong>{label}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            ID: {record.id}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Provider Type',
      dataIndex: 'provider_type',
      key: 'provider_type',
      render: (type: string) => {
        const label = type === 'generic' ? 'Generic Git' : type;
        return <Tag color={PROVIDER_TYPE_COLORS[type] ?? 'default'}>{label}</Tag>;
      },
    },
    {
      title: 'Credential',
      key: 'credential',
      render: (_: unknown, record: SourceProvider) => (
        <Typography.Text>
          {record.credential?.name ?? `ID: ${record.credential_id}`}
        </Typography.Text>
      ),
    },
    {
      title: 'Groups Count',
      key: 'groups_count',
      render: (_: unknown, record: SourceProvider) => (
        <Typography.Text>{record.groups_count ?? '—'}</Typography.Text>
      ),
    },
    {
      title: 'Connection Status',
      key: 'status',
      render: (_: unknown, record: SourceProvider) => (
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
      width: 180,
      render: (_: unknown, record: SourceProvider) => (
        <Space size={4}>
          <PermissionGate permission="source_groups:write">
            <Tooltip title="Edit">
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => {
                  setEditProvider(record);
                  setModalOpen(true);
                }}
              />
            </Tooltip>
          </PermissionGate>
          <Tooltip title="Test Connection">
            <Button
              size="small"
              type="text"
              icon={<PlayCircleOutlined />}
              onClick={() => handleTestConnection(record.id)}
            />
          </Tooltip>
          <PermissionGate permission="source_groups:write">
            <Tooltip title="Delete">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(record.id, record.label)}
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
        <Typography.Title level={4} style={{ margin: 0 }}>
          Source Providers
        </Typography.Title>
        <Space>
          <Select
            style={{ width: 150 }}
            value={typeFilter}
            onChange={(v) => setTypeFilter(v)}
            options={PROVIDER_TYPE_OPTIONS}
          />
          <PermissionGate permission="source_groups:write">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditProvider(undefined);
                setModalOpen(true);
              }}
            >
              Add Provider
            </Button>
          </PermissionGate>
        </Space>
      </Flex>

      {/* ── Content ─────────────────────────────────────────────────────────── */}
      {isLoading && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      )}

      {isError && (
        <Alert
          title="Failed to load providers"
          description="Please try again later."
          type="error"
          showIcon
        />
      )}

      {!isLoading && !isError && (
        <Card>
          <Table
            columns={columns}
            dataSource={filteredProviders as SourceProvider[]}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: <Empty description="No source providers configured" /> }}
          />
        </Card>
      )}

      {/* ── Add/Edit Provider Modal ─────────────────────────────────────────── */}
      <ProviderModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditProvider(undefined);
        }}
        provider={editProvider}
      />
    </Flex>
  );
};

export default ProvidersPage;
