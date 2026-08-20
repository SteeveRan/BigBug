/**
 * @file Pipelines/Projects/index.tsx
 * @description GitLab Projects list page (`/pipelines/projects`). Filterable table
 *              (type / provider / my / search) with Create, Import, Edit and Delete.
 * @dependencies antd, @ant-design/icons, react-router, RTK Query, PermissionGate, StatusChip
 * @relatedFiles ./CreateModal.tsx, ./Detail.tsx
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Alert,
  App,
  Button,
  Card,
  Flex,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DeleteOutlined, EditOutlined, ImportOutlined, PlusOutlined } from '@ant-design/icons';
import {
  useGetGitlabProjectsQuery,
  useGetProvidersQuery,
  useDeleteGitlabProjectMutation,
} from '../../../store/api';
import type { GitlabProject, GitlabProjectType } from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';
import { usePermissions } from '../../../hooks/usePermissions';
import { CreateProjectModal } from './CreateModal';

const TYPE_LABELS: Record<GitlabProjectType, string> = {
  components: 'Components',
  pipelines: 'Pipelines',
};

const TYPE_COLORS: Record<GitlabProjectType, string> = {
  components: 'purple',
  pipelines: 'blue',
};

export function GitlabProjectsPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();

  const [projectType, setProjectType] = useState<GitlabProjectType | undefined>();
  const [providerId, setProviderId] = useState<number | undefined>();
  const [onlyMine, setOnlyMine] = useState(false);
  const [search, setSearch] = useState('');

  const [createOpen, setCreateOpen] = useState(false);

  const {
    data: projects = [],
    isLoading,
    isError,
  } = useGetGitlabProjectsQuery({
    project_type: projectType,
    provider_id: providerId,
    owner: onlyMine ? 'me' : undefined,
    search: search || undefined,
  });
  const { data: providers = [] } = useGetProvidersQuery({ subtype: 'gitlab' });
  const [deleteProject] = useDeleteGitlabProjectMutation();

  const providerMap = useMemo(() => {
    const map = new Map<number, string>();
    providers.forEach((p) => map.set(p.id, p.label));
    return map;
  }, [providers]);

  const handleDelete = async (record: GitlabProject) => {
    try {
      await deleteProject({ id: record.id }).unwrap();
      message.success(`Project "${record.name}" deleted`);
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to delete project');
    }
  };

  const columns: ColumnsType<GitlabProject> = [
    {
      title: 'Name',
      key: 'name',
      render: (_: unknown, record: GitlabProject) => (
        <Flex vertical>
          <Typography.Link strong onClick={() => navigate(`/pipelines/projects/${record.id}`)}>
            {record.name}
          </Typography.Link>
          {record.description && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
              {record.description}
            </Typography.Text>
          )}
        </Flex>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'project_type',
      key: 'project_type',
      width: 120,
      render: (t: GitlabProjectType) => <Tag color={TYPE_COLORS[t]}>{TYPE_LABELS[t]}</Tag>,
    },
    {
      title: 'Provider',
      key: 'provider',
      render: (_: unknown, record: GitlabProject) => (
        <Typography.Text>
          {providerMap.get(record.provider_id) ?? `#${record.provider_id}`}
        </Typography.Text>
      ),
    },
    {
      title: 'Full Path',
      dataIndex: 'full_path',
      key: 'full_path',
      render: (value: string) => (
        <Typography.Text code style={{ fontSize: 12 }}>
          {value}
        </Typography.Text>
      ),
    },
    {
      title: 'Visibility',
      dataIndex: 'visibility',
      key: 'visibility',
      width: 110,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: 'Status',
      key: 'status',
      width: 120,
      render: (_: unknown, record: GitlabProject) => (
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
      width: 160,
      render: (_: unknown, record: GitlabProject) => (
        <Space size={4}>
          <Tooltip title="Open">
            <Button
              size="small"
              type="text"
              icon={<EditOutlined />}
              onClick={() => navigate(`/pipelines/projects/${record.id}`)}
            />
          </Tooltip>
          <PermissionGate permission="gitlab_projects:delete">
            <Popconfirm
              title={`Delete "${record.name}"?`}
              description="This removes the local record (soft delete)."
              onConfirm={() => handleDelete(record)}
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
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Flex vertical gap={4}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            GitLab Projects
          </Typography.Title>
          <Typography.Text type="secondary">
            Component and pipeline projects managed through the GitLab API.
          </Typography.Text>
        </Flex>
        <Space>
          <PermissionGate permission="gitlab_projects:write">
            <Button icon={<ImportOutlined />} onClick={() => setCreateOpen(true)}>
              Import
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              Create Project
            </Button>
          </PermissionGate>
        </Space>
      </Flex>

      <Card>
        <Flex vertical gap={16}>
          <Flex gap={8} wrap="wrap">
            <Select
              style={{ width: 160 }}
              allowClear
              placeholder="Type"
              value={projectType}
              onChange={(v) => setProjectType(v)}
              options={[
                { label: 'Components', value: 'components' },
                { label: 'Pipelines', value: 'pipelines' },
              ]}
            />
            <Select
              style={{ width: 200 }}
              allowClear
              placeholder="Provider"
              value={providerId}
              onChange={(v) => setProviderId(v)}
              options={providers.map((p) => ({ label: p.label, value: p.id }))}
            />
            <Select
              style={{ width: 140 }}
              value={onlyMine ? 'me' : 'all'}
              onChange={(v) => setOnlyMine(v === 'me')}
              options={[
                { label: 'All projects', value: 'all' },
                { label: 'My projects', value: 'me' },
              ]}
            />
            <Input.Search
              style={{ width: 260 }}
              placeholder="Search by name"
              allowClear
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>

          {isError ? (
            <Alert
              type="error"
              title="Failed to load GitLab projects"
              description="Please try again later."
              showIcon
            />
          ) : (
            <Table<GitlabProject>
              columns={columns}
              dataSource={projects}
              rowKey="id"
              loading={isLoading}
              pagination={
                projects.length > 20
                  ? { pageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }
                  : false
              }
              locale={{ emptyText: 'No GitLab projects' }}
            />
          )}
        </Flex>
      </Card>

      <CreateProjectModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        projectType={projectType}
        hasWrite={hasPermission('gitlab_projects:write')}
      />
    </Flex>
  );
}

export default GitlabProjectsPage;
