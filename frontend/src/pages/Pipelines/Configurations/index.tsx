/**
 * @file Configurations/index.tsx
 * @description Страница управления конфигурациями CI/CD пайплайнов — таблица со списком, поиск, модалки
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
  Input,
  App,
  Tooltip,
  Tag,
  Popconfirm,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, CopyOutlined, DeleteOutlined } from '@ant-design/icons';
import {
  useGetPipelineConfigsQuery,
  useDeletePipelineConfigMutation,
  useDuplicatePipelineConfigMutation,
} from '../../../store/api';
import type { PipelineConfig } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';
import { PipelineModal } from './PipelineModal';

const PipelineConfigsPage = () => {
  const { message } = App.useApp();

  const [search, setSearch] = useState('');

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPipeline, setEditingPipeline] = useState<PipelineConfig | null>(null);

  const { data: configs = [], isLoading, isError } = useGetPipelineConfigsQuery();
  const [deleteConfig] = useDeletePipelineConfigMutation();
  const [duplicateConfig] = useDuplicatePipelineConfigMutation();

  // Filter by search
  const filteredConfigs = useMemo(() => {
    if (!search.trim()) return configs;
    const q = search.toLowerCase();
    return configs.filter(
      (c) => c.name.toLowerCase().includes(q) || (c.description?.toLowerCase().includes(q) ?? false)
    );
  }, [configs, search]);

  const handleDelete = async (id: number) => {
    try {
      await deleteConfig(id).unwrap();
      message.success('Pipeline configuration deleted');
    } catch {
      message.error('Failed to delete pipeline configuration');
    }
  };

  const handleDuplicate = async (id: number, name: string) => {
    const newName = `${name} (copy)`;
    try {
      await duplicateConfig({ id, name: newName }).unwrap();
      message.success(`Duplicated as "${newName}"`);
    } catch {
      message.error('Failed to duplicate pipeline configuration');
    }
  };

  const handleEdit = (pipeline: PipelineConfig) => {
    setEditingPipeline(pipeline);
    setModalOpen(true);
  };

  const handleCreate = () => {
    setEditingPipeline(null);
    setModalOpen(true);
  };

  const handleClose = () => {
    setModalOpen(false);
    setEditingPipeline(null);
  };

  const columns: ColumnsType<PipelineConfig> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
      render: (name: string, record: PipelineConfig) => (
        <Flex vertical>
          <Typography.Text strong>{name}</Typography.Text>
          {record.description && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
              {record.description}
            </Typography.Text>
          )}
        </Flex>
      ),
    },
    {
      title: 'GitLab Instance',
      key: 'gitlab_instance',
      render: (_: unknown, record: PipelineConfig) => (
        <Typography.Text>{record.gitlab_instance?.name ?? '—'}</Typography.Text>
      ),
    },
    {
      title: 'Ref',
      dataIndex: 'ref',
      key: 'ref',
      render: (ref: string | null) => <Tag color="blue">{ref || 'main'}</Tag>,
    },
    {
      title: 'Default',
      dataIndex: 'is_default',
      key: 'is_default',
      align: 'center',
      render: (isDefault: boolean) => (isDefault ? <Tag color="green">Default</Tag> : <Tag>—</Tag>),
    },
    {
      title: 'Components',
      key: 'components',
      render: (_: unknown, record: PipelineConfig) => (
        <Tag color="purple">{record.components?.length ?? 0}</Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 180,
      render: (_: unknown, record: PipelineConfig) => (
        <Space size={4}>
          <PermissionGate permission="pipelines:write">
            <Tooltip title="Edit">
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => handleEdit(record)}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="pipelines:write">
            <Tooltip title="Duplicate">
              <Button
                size="small"
                type="text"
                icon={<CopyOutlined />}
                onClick={() => handleDuplicate(record.id, record.name)}
              />
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="pipelines:delete">
            <Popconfirm
              title={`Delete "${record.name}"?`}
              description="This action cannot be undone."
              onConfirm={() => handleDelete(record.id)}
              okText="Delete"
              cancelText="Cancel"
              okButtonProps={{ danger: true }}
            >
              <Tooltip title="Delete">
                <Button size="small" type="text" danger icon={<DeleteOutlined />} />
              </Tooltip>
            </Popconfirm>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Card>
        <Flex justify="space-between" align="center" wrap gap={8}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Pipeline Configurations
          </Typography.Title>
          <PermissionGate permission="pipelines:write">
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              Create Pipeline
            </Button>
          </PermissionGate>
        </Flex>
      </Card>

      <Card>
        <Flex vertical gap={16}>
          <Input.Search
            placeholder="Search by name or description"
            allowClear
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ maxWidth: 400 }}
          />

          <Table<PipelineConfig>
            columns={columns}
            dataSource={filteredConfigs}
            rowKey="id"
            loading={isLoading}
            locale={{
              emptyText: isError
                ? 'Failed to load pipeline configurations'
                : 'No pipeline configurations',
            }}
            pagination={
              filteredConfigs.length > 20
                ? { pageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }
                : false
            }
          />
        </Flex>
      </Card>

      <PipelineModal open={modalOpen} onClose={handleClose} pipeline={editingPipeline} />
    </Flex>
  );
};

export default PipelineConfigsPage;
