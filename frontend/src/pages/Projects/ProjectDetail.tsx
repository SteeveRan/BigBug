/**
 * @file ProjectDetail.tsx
 * @description Страница деталей GitHub проекта: метаданные, описание, README (MarkdownPreview), релизы
 * @dependencies antd, @ant-design/icons, @uiw/react-markdown-preview, Redux store
 */
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Descriptions,
  Tabs,
  Table,
  Tag,
  Flex,
  Spin,
  Space,
  Input,
  Divider,
} from 'antd';
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  LinkOutlined,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import MarkdownPreview from '@uiw/react-markdown-preview';
import {
  useGetProjectQuery,
  useUpdateProjectMutation,
  useRefreshProjectMutation,
} from '../../store/api';
import { GithubProject, GithubRelease } from '../../types';

const releaseColumns = [
  {
    title: 'Tag',
    dataIndex: 'tag_name',
    key: 'tag_name',
    render: (text: string) => <Typography.Text code>{text}</Typography.Text>,
  },
  {
    title: 'Name',
    dataIndex: 'name',
    key: 'name',
    render: (text: string | null) => text ?? <Typography.Text type="secondary">—</Typography.Text>,
  },
  {
    title: 'Pre-release',
    dataIndex: 'is_prerelease',
    key: 'is_prerelease',
    render: (val: boolean) =>
      val ? <Tag color="orange">Pre-release</Tag> : <Typography.Text type="secondary">—</Typography.Text>,
  },
  {
    title: 'Draft',
    dataIndex: 'is_draft',
    key: 'is_draft',
    render: (val: boolean) =>
      val ? <Tag>Draft</Tag> : <Typography.Text type="secondary">—</Typography.Text>,
  },
  {
    title: 'Published',
    dataIndex: 'published_at',
    key: 'published_at',
    render: (val: string | null) =>
      val ? new Date(val).toLocaleDateString() : <Typography.Text type="secondary">—</Typography.Text>,
  },
];

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = Number(id);

  const { data: project, isLoading } = useGetProjectQuery(projectId);
  const [updateProject] = useUpdateProjectMutation();
  const [refreshProject, { isLoading: refreshing }] = useRefreshProjectMutation();

  const [editDesc, setEditDesc] = useState(false);
  const [customDesc, setCustomDesc] = useState('');

  // Releases fetch (backed by GET /projects/{id}/releases — endpoint exists,
  // but not yet exposed as RTK Query hook)
  const [releases, setReleases] = useState<GithubRelease[]>([]);
  const [releasesLoading, setReleasesLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchReleases = async () => {
      setReleasesLoading(true);
      try {
        const res = await fetch(`/api/projects/${projectId}/releases`);
        if (!cancelled && res.ok) {
          const data: GithubRelease[] = await res.json();
          setReleases(data);
        }
      } catch {
        // silently ignore fetch errors
      } finally {
        if (!cancelled) setReleasesLoading(false);
      }
    };
    fetchReleases();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const p = project as GithubProject | undefined;

  const handleEditDesc = () => {
    setCustomDesc(p?.custom_description ?? p?.description ?? '');
    setEditDesc(true);
  };

  const handleSaveDesc = async () => {
    await updateProject({ id: projectId, data: { custom_description: customDesc } });
    setEditDesc(false);
  };

  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: 48 }}>
        <Spin size="large" />
      </Flex>
    );
  }
  if (!p) return <Typography.Title level={5}>Project not found</Typography.Title>;

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex align="center" gap={12} wrap="wrap">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/projects')}>
          Back
        </Button>
        <Typography.Title level={4} style={{ margin: 0, flex: 1 }}>
          {p.full_name}
        </Typography.Title>
        <Space>
          {p.is_stale && <Tag color="warning">Stale</Tag>}
          {p.is_archived && <Tag>Archived</Tag>}
          {p.is_fork && <Tag color="processing">Fork</Tag>}
        </Space>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            loading={refreshing}
            onClick={() => refreshProject(projectId)}
          >
            Refresh from GitHub
          </Button>
          <Button
            icon={<LinkOutlined />}
            href={p.github_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </Button>
        </Space>
      </Flex>

      {/* ── Metadata ────────────────────────────────────────────────────────── */}
      <Card>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
          <Descriptions.Item label="Organization">{p.org.login}</Descriptions.Item>
          <Descriptions.Item label="Default Branch">
            <Typography.Text code>{p.default_branch}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="License">
            {p.license_name ?? p.license_spdx ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Last Synced">
            {p.last_synced_at ? new Date(p.last_synced_at).toLocaleString() : 'Never'}
          </Descriptions.Item>
          <Descriptions.Item label="GitHub Updated">
            {p.github_updated_at ? new Date(p.github_updated_at).toLocaleString() : '—'}
          </Descriptions.Item>
          {p.homepage_url && (
            <Descriptions.Item label="Homepage">
              <Typography.Link href={p.homepage_url} target="_blank" rel="noopener noreferrer">
                {p.homepage_url}
              </Typography.Link>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      {/* ── Tabs: Info / README / Releases ──────────────────────────────────── */}
      <Tabs
        defaultActiveKey="info"
        items={[
          {
            key: 'info',
            label: 'Информация',
            children: (
              <Card>
                <Flex justify="space-between" align="flex-start" style={{ marginBottom: 16 }}>
                  <Typography.Title level={5} style={{ margin: 0 }}>
                    Description
                  </Typography.Title>
                  {!editDesc && (
                    <Button size="small" icon={<EditOutlined />} onClick={handleEditDesc}>
                      Edit
                    </Button>
                  )}
                </Flex>
                {editDesc ? (
                  <Flex vertical gap={8}>
                    <Input.TextArea
                      rows={4}
                      value={customDesc}
                      onChange={(e) => setCustomDesc(e.target.value)}
                      placeholder="Custom description"
                    />
                    <Flex gap={8}>
                      <Button
                        type="primary"
                        size="small"
                        icon={<SaveOutlined />}
                        onClick={handleSaveDesc}
                      >
                        Save
                      </Button>
                      <Button size="small" icon={<CloseOutlined />} onClick={() => setEditDesc(false)}>
                        Cancel
                      </Button>
                    </Flex>
                  </Flex>
                ) : (
                  <Typography.Paragraph type="secondary">
                    {p.custom_description ?? p.description ?? 'No description'}
                  </Typography.Paragraph>
                )}
              </Card>
            ),
          },
          {
            key: 'readme',
            label: 'README',
            children: (
              <Card title="README">
                {p.readme_md ? (
                  <MarkdownPreview source={p.readme_md} />
                ) : (
                  <Typography.Text type="secondary">No README</Typography.Text>
                )}
              </Card>
            ),
          },
          {
            key: 'releases',
            label: 'Релизы',
            children: (
              <Table
                columns={releaseColumns}
                dataSource={releases}
                rowKey="id"
                loading={releasesLoading}
                size="small"
                pagination={{ pageSize: 10, showSizeChanger: false }}
                locale={{ emptyText: 'No releases found' }}
              />
            ),
          },
        ]}
      />
    </Flex>
  );
}
