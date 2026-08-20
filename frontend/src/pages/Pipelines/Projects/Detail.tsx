/**
 * @file Pipelines/Projects/Detail.tsx
 * @description GitLab Project detail page (`/pipelines/projects/:id`). Tabs:
 *              Overview (metadata + Sync), Files (tree + view/edit .yml with push),
 *              Tags (create version), Linked (components or pipelines).
 * @dependencies antd, @ant-design/icons, react-router, RTK Query, PermissionGate, StatusChip
 * @relatedFiles ./index.tsx
 */

import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import {
  Alert,
  App,
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Flex,
  Input,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  CloudSyncOutlined,
  DeleteOutlined,
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import {
  useGetGitlabProjectQuery,
  useSyncGitlabProjectMutation,
  useGetProjectFilesQuery,
  usePushProjectFileMutation,
  useDeleteProjectFileMutation,
  useGetProjectTagsQuery,
  useCreateProjectTagMutation,
  useGetComponentsQuery,
  useGetPipelineConfigsQuery,
} from '../../../store/api';
import type {
  GitlabProject,
  GitlabProjectFile,
  GitlabProjectTag,
  GitLabComponent,
  PipelineConfig,
} from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';

export function GitlabProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const projectId = Number(id);

  const {
    data: project,
    isLoading,
    isError,
  } = useGetGitlabProjectQuery(projectId, { skip: Number.isNaN(projectId) });

  const [syncProject, { isLoading: isSyncing }] = useSyncGitlabProjectMutation();
  const [pushFile, { isLoading: isPushing }] = usePushProjectFileMutation();
  const [deleteFile] = useDeleteProjectFileMutation();
  const [createTag, { isLoading: isTagging }] = useCreateProjectTagMutation();

  const { data: files = [], refetch: refetchFiles } = useGetProjectFilesQuery(
    { id: projectId },
    { skip: Number.isNaN(projectId) }
  );
  const { data: tags = [], refetch: refetchTags } = useGetProjectTagsQuery(projectId, {
    skip: Number.isNaN(projectId),
  });
  const { data: components = [] } = useGetComponentsQuery(
    { gitlab_project_id: projectId },
    { skip: Number.isNaN(projectId) }
  );
  const { data: configs = [] } = useGetPipelineConfigsQuery();

  // File editor state
  const [fileModalOpen, setFileModalOpen] = useState(false);
  const [editingFile, setEditingFile] = useState<GitlabProjectFile | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [newFilePath, setNewFilePath] = useState('');

  // Tag modal state
  const [tagModalOpen, setTagModalOpen] = useState(false);
  const [tagName, setTagName] = useState('');
  const [tagRef, setTagRef] = useState('');

  const linkedPipelines = useMemo(
    () => (configs as PipelineConfig[]).filter((c) => c.gitlab_project_id === projectId),
    [configs, projectId]
  );

  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: '48px 0' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  if (isError || !project) {
    return (
      <Flex vertical gap={16}>
        <Alert
          type="error"
          title="Failed to load GitLab project"
          description="Please check the project ID and try again."
          showIcon
        />
      </Flex>
    );
  }

  const p = project as GitlabProject;

  const handleSync = async () => {
    try {
      await syncProject(p.id).unwrap();
      message.success('Project synced');
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Sync failed');
    }
  };

  const openEditFile = (file: GitlabProjectFile) => {
    setEditingFile(file);
    setFileContent(file.content ?? '');
    setFileModalOpen(true);
  };

  const openNewFile = () => {
    setEditingFile(null);
    setFileContent('');
    setNewFilePath('');
    setFileModalOpen(true);
  };

  const handleSaveFile = async () => {
    try {
      await pushFile({
        id: p.id,
        data: {
          file_path: editingFile?.path ?? newFilePath,
          content: fileContent,
          commit_message: `Update ${editingFile?.path ?? newFilePath} via BigBug`,
        },
      }).unwrap();
      message.success('File pushed');
      setFileModalOpen(false);
      refetchFiles();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to push file');
    }
  };

  const handleDeleteFile = async (filePath: string) => {
    try {
      await deleteFile({ id: p.id, file_path: filePath }).unwrap();
      message.success('File deleted');
      refetchFiles();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to delete file');
    }
  };

  const handleCreateTag = async () => {
    try {
      await createTag({
        id: p.id,
        data: { tag_name: tagName, ref: tagRef || undefined },
      }).unwrap();
      message.success('Tag created');
      setTagModalOpen(false);
      setTagName('');
      setTagRef('');
      refetchTags();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to create tag');
    }
  };

  const fileColumns: ColumnsType<GitlabProjectFile> = [
    {
      title: 'Path',
      dataIndex: 'path',
      key: 'path',
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 90,
      render: (v: string | null) => <Tag>{v ?? '—'}</Tag>,
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 140,
      render: (_: unknown, record: GitlabProjectFile) => (
        <Space size={4}>
          <PermissionGate permission="gitlab_projects:write">
            <Tooltip title="Edit">
              <Button
                size="small"
                type="text"
                icon={<SaveOutlined />}
                onClick={() => openEditFile(record)}
              />
            </Tooltip>
            <Popconfirm
              title={`Delete "${record.path}"?`}
              onConfirm={() => handleDeleteFile(record.path)}
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

  const tagColumns: ColumnsType<GitlabProjectTag> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: 'Target',
      dataIndex: 'target',
      key: 'target',
      width: 200,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: 'Message',
      dataIndex: 'message',
      key: 'message',
      render: (v: string | null) => v ?? '—',
    },
  ];

  const componentColumns: ColumnsType<GitLabComponent> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Component Path',
      dataIndex: 'component_path',
      key: 'component_path',
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: 'Version',
      dataIndex: 'version',
      key: 'version',
      width: 120,
      render: (v: string | null) => v ?? '—',
    },
  ];

  const pipelineColumns: ColumnsType<PipelineConfig> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Ref',
      dataIndex: 'ref',
      key: 'ref',
      width: 120,
      render: (v: string | null) => <Tag color="blue">{v ?? 'main'}</Tag>,
    },
    {
      title: 'Components',
      key: 'components',
      width: 120,
      render: (_: unknown, r: PipelineConfig) => (
        <Tag color="purple">{r.components?.length ?? 0}</Tag>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Breadcrumb
        items={[
          { title: 'GitLab Projects', onClick: () => navigate('/pipelines/projects') },
          { title: p.name },
        ]}
      />

      <Flex align="center" gap={12} wrap="wrap">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/pipelines/projects')}>
          Back
        </Button>
        <Typography.Title level={4} style={{ margin: 0, flex: 1 }}>
          {p.name}
        </Typography.Title>
        <Tag color={p.project_type === 'components' ? 'purple' : 'blue'}>{p.project_type}</Tag>
        <StatusChip statusFlag={p.status_flag as 0 | 1 | 2 | 3 | 4} statusText={p.status_text} />
        <PermissionGate permission="gitlab_projects:write">
          <Button icon={<CloudSyncOutlined />} loading={isSyncing} onClick={handleSync}>
            Sync
          </Button>
        </PermissionGate>
      </Flex>

      <Tabs
        items={[
          {
            key: 'overview',
            label: 'Overview',
            children: (
              <Card>
                <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
                  <Descriptions.Item label="Full Path">
                    <Typography.Text code>{p.full_path}</Typography.Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Web URL">
                    {p.web_url ? (
                      <a href={p.web_url} target="_blank" rel="noopener noreferrer">
                        {p.web_url}
                      </a>
                    ) : (
                      '—'
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label="Namespace">{p.namespace_path}</Descriptions.Item>
                  <Descriptions.Item label="Default Branch">{p.default_branch}</Descriptions.Item>
                  <Descriptions.Item label="GitLab Visibility">
                    {p.gitlab_visibility ?? '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Visibility">{p.visibility}</Descriptions.Item>
                  <Descriptions.Item label="External ID">{p.external_id ?? '—'}</Descriptions.Item>
                  <Descriptions.Item label="Description">{p.description ?? '—'}</Descriptions.Item>
                  <Descriptions.Item label="Last Synced">
                    {p.last_synced_at ? new Date(p.last_synced_at).toLocaleString() : '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Created">
                    {new Date(p.created_at).toLocaleString()}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            ),
          },
          {
            key: 'files',
            label: `Files (${files.length})`,
            children: (
              <Card>
                <Flex vertical gap={16}>
                  <PermissionGate permission="gitlab_projects:write">
                    <Button type="primary" icon={<PlusOutlined />} onClick={openNewFile}>
                      New File
                    </Button>
                  </PermissionGate>
                  <Table<GitlabProjectFile>
                    columns={fileColumns}
                    dataSource={files}
                    rowKey="path"
                    pagination={false}
                    locale={{ emptyText: 'No files' }}
                  />
                </Flex>
              </Card>
            ),
          },
          {
            key: 'tags',
            label: `Tags (${tags.length})`,
            children: (
              <Card>
                <Flex vertical gap={16}>
                  <PermissionGate permission="gitlab_projects:write">
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => setTagModalOpen(true)}
                    >
                      Create Tag
                    </Button>
                  </PermissionGate>
                  <Table<GitlabProjectTag>
                    columns={tagColumns}
                    dataSource={tags}
                    rowKey="name"
                    pagination={false}
                    locale={{ emptyText: 'No tags' }}
                  />
                </Flex>
              </Card>
            ),
          },
          {
            key: 'linked',
            label: 'Linked',
            children:
              p.project_type === 'components' ? (
                <Card>
                  <Table<GitLabComponent>
                    columns={componentColumns}
                    dataSource={components as GitLabComponent[]}
                    rowKey="id"
                    pagination={false}
                    locale={{ emptyText: 'No linked components' }}
                  />
                </Card>
              ) : (
                <Card>
                  <Table<PipelineConfig>
                    columns={pipelineColumns}
                    dataSource={linkedPipelines}
                    rowKey="id"
                    pagination={false}
                    locale={{ emptyText: 'No linked pipelines' }}
                  />
                </Card>
              ),
          },
        ]}
      />

      {/* File editor modal */}
      <Modal
        title={editingFile ? `Edit ${editingFile.path}` : 'New File'}
        open={fileModalOpen}
        onCancel={() => setFileModalOpen(false)}
        onOk={handleSaveFile}
        confirmLoading={isPushing}
        okText="Push"
        cancelText="Cancel"
        width={720}
      >
        {!editingFile && (
          <Input
            placeholder="file/path.yml"
            value={newFilePath}
            onChange={(e) => setNewFilePath(e.target.value)}
            style={{ marginBottom: 12 }}
          />
        )}
        <Input.TextArea
          value={fileContent}
          onChange={(e) => setFileContent(e.target.value)}
          rows={20}
          style={{ fontFamily: 'monospace' }}
        />
      </Modal>

      {/* Tag creation modal */}
      <Modal
        title="Create Tag"
        open={tagModalOpen}
        onCancel={() => setTagModalOpen(false)}
        onOk={handleCreateTag}
        confirmLoading={isTagging}
        okText="Create"
        cancelText="Cancel"
      >
        <Flex vertical gap={12}>
          <Input
            placeholder="tag name (e.g. v1.0.0)"
            value={tagName}
            onChange={(e) => setTagName(e.target.value)}
          />
          <Input
            placeholder="ref (optional, defaults to default branch)"
            value={tagRef}
            onChange={(e) => setTagRef(e.target.value)}
          />
        </Flex>
      </Modal>
    </Flex>
  );
}

export default GitlabProjectDetailPage;
