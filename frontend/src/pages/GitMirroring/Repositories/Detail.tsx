/**
 * @file Repositories/Detail.tsx
 * @description Страница детализации Source Repository с табами: Info (блоки), Releases, README
 * @dependencies antd, react-router, RTK Query
 */

import { useState, useMemo } from 'react';
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
  App,
  Row,
  Col,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  LinkOutlined,
  GithubOutlined,
  StarOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
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
  const { message } = App.useApp();
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

  const [refreshRepository, { isLoading: refreshLoading }] = useRefreshSourceRepositoryMutation();

  // Fetch releases (when releases or info tab is active — info tab needs pre-release data)
  const { data: releases = [], isLoading: releasesLoading } = useGetRepositoryReleasesQuery(
    { repository_id: repositoryId, include_prereleases: true },
    { skip: (activeTab !== 'releases' && activeTab !== 'info') || isNaN(repositoryId) }
  );

  // Latest pre-release for Activity block
  const latestPrerelease = useMemo(() => {
    if (activeTab !== 'info') return null;
    return releases.filter((r: SourceRepositoryRelease) => r.is_prerelease)[0] ?? null;
  }, [releases, activeTab]);

  // Fetch README (only when readme tab is active)
  const {
    data: readme,
    isLoading: readmeLoading,
    isError: readmeError,
  } = useGetRepositoryReadmeQuery(repositoryId, {
    skip: activeTab !== 'readme' || isNaN(repositoryId) || !repo?.readme_html,
  });

  // Fetch mirrors (now loaded for Info tab)
  const mirrorsParams: MirrorFilters = { limit: 100 };
  const { data: mirrors = [], isLoading: mirrorsLoading } = useGetMirrorsQuery(mirrorsParams, {
    skip: activeTab !== 'info',
  });

  // Filter mirrors for this specific source repository
  const repoMirrors = mirrors.filter((m: Mirror) => m.source_repository_id === repositoryId);

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
        <Flex vertical gap={16}>
          {/* ── Block 1: Two-column repository info ──────────────────────────── */}
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Card title="Repository Info" style={{ height: '100%' }}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="Full Name">
                    <Typography.Text strong>{repo.full_name}</Typography.Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Description">
                    {repo.description ?? '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Web URL">
                    {repo.web_url ? (
                      <Button
                        type="link"
                        icon={<GithubOutlined />}
                        href={repo.web_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ padding: 0 }}
                      >
                        {repo.web_url}
                      </Button>
                    ) : (
                      '—'
                    )}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card title="Details" style={{ height: '100%' }}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="Stars">
                    <Space>
                      <StarOutlined />
                      {repo.stars_count}
                    </Space>
                  </Descriptions.Item>
                  <Descriptions.Item label="License">
                    {repo.license_spdx ? <Tag>{repo.license_spdx}</Tag> : '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Archived">
                    {repo.is_archived ? <Tag color="warning">Yes</Tag> : 'No'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Fork">
                    {repo.is_fork ? <Tag color="processing">Yes</Tag> : 'No'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Language">
                    {repo.language ? <Tag>{repo.language}</Tag> : '—'}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
          </Row>

          {/* ── Block 2: Activity ──────────────────────────────────────────────── */}
          <Card title="Activity">
            <Descriptions column={{ xs: 1, sm: 2 }} size="small" bordered>
              <Descriptions.Item label="Last Commit">
                {repo.source_pushed_at ? new Date(repo.source_pushed_at).toLocaleString() : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Last Commit Date">
                {repo.source_pushed_at ? new Date(repo.source_pushed_at).toLocaleDateString() : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Latest Release">
                {repo.latest_release_tag ? (
                  <Space>
                    <Typography.Text code>{repo.latest_release_tag}</Typography.Text>
                    {repo.latest_release_name && (
                      <Typography.Text type="secondary">
                        ({repo.latest_release_name})
                      </Typography.Text>
                    )}
                  </Space>
                ) : (
                  '—'
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Latest Release Date">
                {repo.latest_release_date
                  ? new Date(repo.latest_release_date).toLocaleString()
                  : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Latest Pre-release">
                {latestPrerelease?.release_tag ? (
                  <Typography.Text code>{latestPrerelease.release_tag}</Typography.Text>
                ) : (
                  '—'
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Latest Pre-release Date">
                {latestPrerelease?.published_at
                  ? new Date(latestPrerelease.published_at).toLocaleString()
                  : '—'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* ── Block 3: Mirrors table ──────────────────────────────────────────── */}
          <Card title={`Mirrors (${repoMirrors.length})`}>
            <Table
              columns={mirrorColumns}
              dataSource={repoMirrors as Mirror[]}
              rowKey="id"
              loading={mirrorsLoading}
              pagination={false}
              locale={{ emptyText: <Empty description="No mirrors for this repository" /> }}
            />
          </Card>
        </Flex>
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
        itemRender={(route, _params, routes) => {
          const last = routes.indexOf(route) === routes.length - 1;
          if (last) return <span>{route.title}</span>;
          return (
            <a
              onClick={(e) => {
                e.preventDefault();
                (route.onClick as (e: React.MouseEvent) => void)?.(e);
              }}
            >
              {route.title}
            </a>
          );
        }}
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
