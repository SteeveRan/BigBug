/**
 * @file Repositories/Detail.tsx
 * @description Страница детализации Source Repository с табами (Group F)
 * @dependencies antd, react-router, RTK Query
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Tabs,
  Descriptions,
  Table,
  Tag,
  Button,
  Flex,
  Space,
  Spin,
  Alert,
  Empty,
  Switch,
  Breadcrumb,
  Tooltip,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { LinkOutlined, GithubOutlined, StarOutlined, ForkOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  useGetSourceRepositoryQuery,
  useGetRepositoryReleasesQuery,
  useGetRepositoryReadmeQuery,
  useGetMirrorsQuery,
  useRefreshSourceRepositoryMutation,
} from '../../../store/api';
import type { SourceRepositoryRelease, Mirror, MirrorFilters } from '../../../types';
import { StatusChip } from '../../../components/StatusChip';

const RepositoryDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const repositoryId = Number(id);

  const [includePrereleases, setIncludePrereleases] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('info');

  // Fetch repository detail
  const {
    data: repo,
    isLoading: repoLoading,
    isError: repoError,
  } = useGetSourceRepositoryQuery(repositoryId, { skip: isNaN(repositoryId) });

  const [refreshRepository, { isLoading: refreshLoading }] =
    useRefreshSourceRepositoryMutation();

  // Fetch releases (only when releases tab is active)
  const { data: releases = [], isLoading: releasesLoading } = useGetRepositoryReleasesQuery(
    { repository_id: repositoryId, include_prereleases: includePrereleases },
    { skip: activeTab !== 'releases' || isNaN(repositoryId) }
  );

  // Fetch README (only when readme tab is active)
  const {
    data: readme,
    isLoading: readmeLoading,
    isError: readmeError,
  } = useGetRepositoryReadmeQuery(repositoryId, {
    skip: activeTab !== 'readme' || isNaN(repositoryId) || !repo?.readme_html,
  });

  // Fetch mirrors for this repo
  const mirrorsParams: MirrorFilters = { limit: 100 };
  const { data: mirrors = [], isLoading: mirrorsLoading } = useGetMirrorsQuery(mirrorsParams, {
    skip: activeTab !== 'mirrors',
  });

  // Filter mirrors for this specific source repository
  const repoMirrors = mirrors.filter((m) => m.source_repository_id === repositoryId);

  if (repoLoading) {
    return (
      <Flex justify="center" style={{ padding: '40px 0' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  if (repoError || !repo) {
    return (
      <Alert
        message="Failed to load repository"
        description="Please check the repository ID and try again."
        type="error"
        showIcon
      />
    );
  }

  const releaseColumns: ColumnsType<SourceRepositoryRelease> = [
    {
      title: 'Tag',
      dataIndex: 'release_tag',
      key: 'release_tag',
      render: (tag: string) => <Typography.Text code>{tag}</Typography.Text>,
    },
    {
      title: 'Name',
      dataIndex: 'release_name',
      key: 'release_name',
      render: (name: string | undefined) => name ?? '—',
    },
    {
      title: 'Published At',
      dataIndex: 'published_at',
      key: 'published_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: 'Prerelease',
      dataIndex: 'is_prerelease',
      key: 'is_prerelease',
      render: (val: boolean) =>
        val ? <Tag color="orange">Pre-release</Tag> : <Tag color="green">Stable</Tag>,
    },
    {
      title: 'Link',
      key: 'link',
      render: (_: unknown, record: SourceRepositoryRelease) => (
        <Tooltip title="Open release">
          <Button
            size="small"
            type="link"
            icon={<LinkOutlined />}
            href={record.html_url}
            target="_blank"
            rel="noopener noreferrer"
          />
        </Tooltip>
      ),
    },
  ];

  const mirrorColumns: ColumnsType<Mirror> = [
    {
      title: 'Target Path',
      dataIndex: 'target_path',
      key: 'target_path',
    },
    {
      title: 'Sync Group',
      key: 'sync_group',
      render: (_: unknown, record: Mirror) => record.sync_group_name ?? record.sync_group_id,
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: Mirror) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Last Sync',
      key: 'last_sync',
      render: (_: unknown, record: Mirror) =>
        record.last_sync_at ? new Date(record.last_sync_at).toLocaleString() : '—',
    },
  ];

  const tabItems = [
    {
      key: 'info',
      label: 'Info',
      children: (
        <Card>
          <Descriptions bordered column={{ xs: 1, sm: 2 }}>
            <Descriptions.Item label="Name">{repo.name}</Descriptions.Item>
            <Descriptions.Item label="Full Name">{repo.full_name}</Descriptions.Item>
            <Descriptions.Item label="Description" span={{ xs: 1, sm: 2 }}>
              {repo.description ?? '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Language">
              {repo.language ? <Tag>{repo.language}</Tag> : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Default Branch">
              <Typography.Text code>{repo.default_branch}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="Stars">
              <Space>
                <StarOutlined />
                {repo.stars_count}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="Forks">
              <Space>
                <ForkOutlined />
                {repo.forks_count}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="Archived">
              {repo.is_archived ? <Tag color="warning">Yes</Tag> : 'No'}
            </Descriptions.Item>
            <Descriptions.Item label="Fork">
              {repo.is_fork ? <Tag color="processing">Yes</Tag> : 'No'}
            </Descriptions.Item>
            <Descriptions.Item label="Private">
              {repo.is_private ? <Tag>Yes</Tag> : 'No'}
            </Descriptions.Item>
            <Descriptions.Item label="License">
              {repo.license_spdx ? <Tag>{repo.license_spdx}</Tag> : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Web URL" span={{ xs: 1, sm: 2 }}>
              {repo.web_url ? (
                <Button
                  type="link"
                  icon={<GithubOutlined />}
                  href={repo.web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {repo.web_url}
                </Button>
              ) : (
                '—'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Latest Release">
              {repo.latest_release_tag ? (
                <Typography.Text code>{repo.latest_release_tag}</Typography.Text>
              ) : (
                '—'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Latest Release Date">
              {repo.latest_release_date
                ? new Date(repo.latest_release_date).toLocaleString()
                : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Has README">
              {repo.readme_html ? <Tag color="green">Yes</Tag> : <Tag color="default">No</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="Mirrors Count">{repo.mirrors?.length ?? '—'}</Descriptions.Item>
          </Descriptions>
        </Card>
      ),
    },
    {
      key: 'releases',
      label: 'Releases',
      children: (
        <Flex vertical gap={16}>
          <Flex justify="flex-end">
            <Space>
              <Typography.Text>Include pre-releases:</Typography.Text>
              <Switch checked={includePrereleases} onChange={(v) => setIncludePrereleases(v)} />
            </Space>
          </Flex>
          <Card>
            <Table
              columns={releaseColumns}
              dataSource={releases as SourceRepositoryRelease[]}
              rowKey="id"
              loading={releasesLoading}
              pagination={false}
              locale={{ emptyText: <Empty description="No releases found" /> }}
            />
          </Card>
        </Flex>
      ),
    },
    {
      key: 'readme',
      label: 'README',
      children: (
        <Card>
          {readmeLoading && (
            <Flex justify="center" style={{ padding: '40px 0' }}>
              <Spin />
            </Flex>
          )}
          {readmeError && (
            <Alert
              message="Failed to load README"
              description="Please try again later."
              type="error"
              showIcon
            />
          )}
          {!readmeLoading && !readmeError && !readme?.html && (
            <Empty description="No README available" />
          )}
          {readme?.html && (
            <div
              dangerouslySetInnerHTML={{ __html: readme.html }}
              style={{ maxWidth: '100%', overflow: 'auto' }}
            />
          )}
        </Card>
      ),
    },
    {
      key: 'mirrors',
      label: `Mirrors (${repoMirrors.length})`,
      children: (
        <Card>
          <Table
            columns={mirrorColumns}
            dataSource={repoMirrors as Mirror[]}
            rowKey="id"
            loading={mirrorsLoading}
            pagination={false}
            locale={{ emptyText: <Empty description="No mirrors for this repository" /> }}
          />
        </Card>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Breadcrumbs ─────────────────────────────────────────────────────── */}
      <Breadcrumb
        items={[
          { title: 'Git Mirroring', onClick: () => navigate('/git-mirroring/mirrors') },
          { title: 'Repositories', onClick: () => navigate('/git-mirroring/repositories') },
          { title: repo.name },
        ]}
      />

      {/* ── Title ───────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {repo.full_name}
        </Typography.Title>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            loading={refreshLoading}
            onClick={async () => {
              try {
                await refreshRepository(repositoryId).unwrap();
                message.success('Metadata refreshed successfully');
              } catch (err: unknown) {
                const msg =
                  err && typeof err === 'object' && 'data' in err
                    ? (err as { data?: { detail?: string } }).data?.detail
                    : undefined;
                message.error(msg ?? 'Failed to refresh metadata');
              }
            }}
          >
            Refresh Metadata
          </Button>
          {repo.web_url && (
            <Button
              icon={<GithubOutlined />}
              href={repo.web_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open on GitHub
            </Button>
          )}
        </Space>
      </Flex>

      {/* ── Tabs ────────────────────────────────────────────────────────────── */}
      <Card>
        <Tabs activeKey={activeTab} onChange={(key) => setActiveTab(key)} items={tabItems} />
      </Card>
    </Flex>
  );
};

export default RepositoryDetailPage;
