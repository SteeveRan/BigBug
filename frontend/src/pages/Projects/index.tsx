/**
 * @file index.tsx
 * @description Страница списка GitHub проектов: таблица с columns/dataSource, модальное окно импорта/добавления
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Table,
  Tag,
  Flex,
  Space,
  Modal,
  Input,
  App,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, ReloadOutlined, ExportOutlined, WarningOutlined } from '@ant-design/icons';
import {
  useListProjectsQuery,
  useCreateProjectMutation,
  useImportProjectMutation,
  useRefreshProjectMutation,
} from '../../store/api';
import { GithubProject } from '../../types';

export function ProjectsPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { data: projects = [], isLoading } = useListProjectsQuery();
  const [createProject] = useCreateProjectMutation();
  const [importProject] = useImportProjectMutation();
  const [refreshProject] = useRefreshProjectMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [githubUrl, setGithubUrl] = useState('');
  const [gitlabUrl, setGitlabUrl] = useState('');
  const [isImport, setIsImport] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleAdd = () => {
    setIsImport(false);
    setGithubUrl('');
    setGitlabUrl('');
    setDialogOpen(true);
  };

  const handleImport = () => {
    setIsImport(true);
    setGithubUrl('');
    setGitlabUrl('');
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      if (isImport) {
        await importProject({ github_url: githubUrl, gitlab_url: gitlabUrl || undefined }).unwrap();
        message.success('Project imported successfully');
      } else {
        await createProject({ github_url: githubUrl }).unwrap();
        message.success('Project added successfully');
      }
      setDialogOpen(false);
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  const columns: ColumnsType<GithubProject> = [
    {
      title: 'Project',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: GithubProject) => (
        <Flex vertical>
          <Space>
            <Typography.Link
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/projects/${record.id}`);
              }}
            >
              {name}
            </Typography.Link>
            {record.is_stale && (
              <Tooltip title="Stale — not synced recently">
                <WarningOutlined style={{ color: '#faad14' }} />
              </Tooltip>
            )}
          </Space>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.full_name}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Organization',
      dataIndex: ['org', 'login'],
      key: 'organization',
    },
    {
      title: 'License',
      dataIndex: 'license_spdx',
      key: 'license_spdx',
      render: (license: string | null) =>
        license ? <Tag>{license}</Tag> : <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: 'Last Synced',
      dataIndex: 'last_synced_at',
      key: 'last_synced_at',
      render: (val: string | null) =>
        val ? (
          new Date(val).toLocaleDateString()
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: GithubProject) => (
        <Space size={4}>
          {record.is_archived && <Tag>Archived</Tag>}
          {record.is_fork && <Tag color="processing">Fork</Tag>}
        </Space>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: GithubProject) => (
        <Space>
          <Tooltip title="Refresh from GitHub">
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                refreshProject(record.id);
              }}
            />
          </Tooltip>
          <Tooltip title="Open on GitHub">
            <Button
              size="small"
              icon={<ExportOutlined />}
              href={record.github_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          GitHub Projects
        </Typography.Title>
        <Space>
          <Button icon={<ExportOutlined />} onClick={handleImport}>
            Import Existing
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            Add Project
          </Button>
        </Space>
      </Flex>

      {/* ── Table ───────────────────────────────────────────────────────────── */}
      <Card>
        <Table
          columns={columns}
          dataSource={projects as GithubProject[]}
          rowKey="id"
          loading={isLoading}
          onRow={(record) => ({
            onClick: () => navigate(`/projects/${record.id}`),
            style: { cursor: 'pointer' },
          })}
          pagination={false}
          locale={{ emptyText: 'No projects yet. Add a GitHub project to get started.' }}
        />
      </Card>

      {/* ── Import / Add Modal ──────────────────────────────────────────────── */}
      <Modal
        title={isImport ? 'Import Existing Mirror' : 'Add GitHub Project'}
        open={dialogOpen}
        onOk={handleSubmit}
        onCancel={() => setDialogOpen(false)}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !githubUrl }}
        okText={isImport ? 'Import' : 'Add'}
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="https://github.com/owner/repo"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
          />
          {isImport && (
            <Input
              placeholder="https://gitlab.example.com/namespace/repo"
              value={gitlabUrl}
              onChange={(e) => setGitlabUrl(e.target.value)}
            />
          )}
        </Space>
      </Modal>
    </Flex>
  );
}
