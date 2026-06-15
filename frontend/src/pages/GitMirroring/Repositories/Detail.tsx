/**
 * @file Repositories/Detail.tsx
 * @description Страница детализации Source Repository с табами: Info (блоки), Releases, README
 * @dependencies antd, react-router, RTK Query
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router';
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
  Skeleton,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  LinkOutlined,
  GithubOutlined,
  StarOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import XMarkdown from '@ant-design/x-markdown';
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
  const [searchParams, setSearchParams] = useSearchParams();
  const repositoryId = Number(id);

  // Sync active tab with URL ?tab= parameter
  const tabFromUrl = searchParams.get('tab') ?? 'info';
  const validTabs = ['info', 'releases', 'readme'];
  const activeTab = validTabs.includes(tabFromUrl) ? tabFromUrl : 'info';

  const setActiveTab = (tab: string) => {
    setSearchParams({ tab }, { replace: true });
  };

  const [includePrereleases, setIncludePrereleases] = useState(false);

  // Fetch repository detail
  const {
    data: repo,
    isLoading: repoLoading,
    isError: repoError,
    refetch: refetchRepo,
  } = useGetSourceRepositoryQuery(repositoryId, {
    skip: isNaN(repositoryId),
  });

  // Reactive polling: poll every 3s while status_flag === 3
  useEffect(() => {
    if (repo?.status_flag !== 3) return;
    const interval = setInterval(() => {
      refetchRepo();
    }, 3000);
    return () => clearInterval(interval);
  }, [repo?.status_flag, refetchRepo]);

  const [refreshRepository, { isLoading: refreshLoading }] = useRefreshSourceRepositoryMutation();

  // Fetch releases (only when releases tab is active, refetch on tab switch)
  const { data: releases = [], isLoading: releasesLoading } = useGetRepositoryReleasesQuery(
    { repository_id: repositoryId, include_prereleases: true },
    { skip: activeTab !== 'releases' || isNaN(repositoryId), refetchOnMountOrArgChange: true }
  );

  // Fetch README (only when readme tab is active, refetch on tab switch)
  const {
    data: readme,
    isLoading: readmeLoading,
    isError: readmeError,
  } = useGetRepositoryReadmeQuery(repositoryId, {
    skip: activeTab !== 'readme' || isNaN(repositoryId),
    refetchOnMountOrArgChange: true,
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
        title="Failed to load repository"
        description="Please check the repository ID and try again."
        type="error"
        showIcon
      />
    );
  }

  // Determine if metadata is currently being fetched
  const isFetching = repo.status_flag === 3;
  const providerType = repo.source_provider?.provider_type ?? repo.provider_type ?? '—';

  // Helper: build commit/release URL from clone_url
  const buildCommitUrl = (sha: string) => {
    const base = repo.clone_url_https || repo.web_url || '';
    if (!base || !sha) return null;
    // Strip .git suffix
    const cleanBase = base.replace(/\.git$/, '');
    // GitHub/GitLab commit URL pattern
    return `${cleanBase}/commit/${sha}`;
  };

  // Format ISO date for display (dd.mm.yy HH:MM:SS, 24h)
  const formatDate = (dateStr: string | null | undefined): string => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      const dd = String(d.getDate()).padStart(2, '0');
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const yy = String(d.getFullYear()).slice(-2);
      const hh = String(d.getHours()).padStart(2, '0');
      const min = String(d.getMinutes()).padStart(2, '0');
      const ss = String(d.getSeconds()).padStart(2, '0');
      return `${dd}.${mm}.${yy} ${hh}:${min}:${ss}`;
    } catch {
      return dateStr;
    }
  };

  const releaseColumns: ColumnsType<SourceRepositoryRelease> = [
    {
      title: 'Tag',
      dataIndex: 'tag',
      key: 'tag',
      render: (tag: string) => <Typography.Text code>{tag}</Typography.Text>,
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string | undefined) => name ?? '—',
    },
    {
      title: 'Published At',
      dataIndex: 'published_at',
      key: 'published_at',
      render: (date: string) => formatDate(date),
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
            href={record.url}
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
        record.last_sync_at ? formatDate(record.last_sync_at) : '—',
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
                    {isFetching ? (
                      <Skeleton.Input active size="small" block />
                    ) : (
                      repo.description ?? '—'
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label="Provider Type">
                    <Tag>{providerType}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Web URL">
                    {isFetching ? (
                      <Skeleton.Input active size="small" block />
                    ) : repo.web_url ? (
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
                    {isFetching ? (
                      <Skeleton.Input active size="small" />
                    ) : (
                      <Space>
                        <StarOutlined />
                        {repo.stars_count}
                      </Space>
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label="License">
                    {isFetching ? (
                      <Skeleton.Input active size="small" />
                    ) : repo.license_spdx ? (
                      <Tag>{repo.license_spdx}</Tag>
                    ) : (
                      '—'
                    )}
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

          {/* ── Block 2: Activity in 3 columns ────────────────────────────────── */}
          <Card title="Activity">
            <Row gutter={16}>
              {/* ── Last Commit ─────────────────────────────────────────────── */}
              <Col xs={24} sm={8}>
                <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
                  Last Commit
                </Typography.Text>
                {isFetching ? (
                  <Skeleton active paragraph={{ rows: 2 }} />
                ) : repo.last_commit_sha ? (
                  <Flex vertical gap={4}>
                    {buildCommitUrl(repo.last_commit_sha) ? (
                      <Typography.Link
                        href={buildCommitUrl(repo.last_commit_sha)!}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontFamily: 'monospace', fontSize: 14 }}
                      >
                        {repo.last_commit_sha.substring(0, 7)}
                      </Typography.Link>
                    ) : (
                      <Typography.Text code>{repo.last_commit_sha.substring(0, 7)}</Typography.Text>
                    )}
                    <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                      {formatDate(repo.last_commit_date)}
                    </Typography.Text>
                    {repo.last_commit_message && (
                      <Typography.Text type="secondary" ellipsis style={{ fontSize: 13 }}>
                        {repo.last_commit_message}
                      </Typography.Text>
                    )}
                  </Flex>
                ) : (
                  <Typography.Text type="secondary">No data</Typography.Text>
                )}
              </Col>

              {/* ── Latest Release ──────────────────────────────────────────── */}
              <Col xs={24} sm={8}>
                <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
                  Latest Release
                </Typography.Text>
                {isFetching ? (
                  <Skeleton active paragraph={{ rows: 2 }} />
                ) : repo.latest_release_tag ? (
                  <Flex vertical gap={4}>
                    <Typography.Text strong style={{ fontSize: 15 }}>
                      {repo.latest_release_name || repo.latest_release_tag}
                    </Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                      {formatDate(repo.latest_release_date)}
                    </Typography.Text>
                    {repo.latest_release_url && (
                      <Typography.Link
                        href={repo.latest_release_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: 13 }}
                      >
                        View release <LinkOutlined />
                      </Typography.Link>
                    )}
                  </Flex>
                ) : (
                  <Typography.Text type="secondary">No data</Typography.Text>
                )}
              </Col>

              {/* ── Latest Pre-release ───────────────────────────────────────── */}
              <Col xs={24} sm={8}>
                <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
                  Latest Pre-release
                </Typography.Text>
                {isFetching ? (
                  <Skeleton active paragraph={{ rows: 2 }} />
                ) : repo.latest_prerelease_tag ? (
                  <Flex vertical gap={4}>
                    <Typography.Text strong style={{ fontSize: 15 }}>
                      {repo.latest_prerelease_name || repo.latest_prerelease_tag}
                    </Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                      {formatDate(repo.latest_prerelease_date)}
                    </Typography.Text>
                    {repo.latest_prerelease_url && (
                      <Typography.Link
                        href={repo.latest_prerelease_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: 13 }}
                      >
                        View release <LinkOutlined />
                      </Typography.Link>
                    )}
                  </Flex>
                ) : (
                  <Typography.Text type="secondary">No data</Typography.Text>
                )}
              </Col>
            </Row>
          </Card>

          {/* ── Block 3: README ──────────────────────────────────────────────── */}
          {repo.readme_html && (
            <Card title="README">
              <XMarkdown content={repo.readme_html} openLinksInNewTab />
            </Card>
          )}

          {/* ── Block 4: Mirrors table ──────────────────────────────────────────── */}
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
              title="Failed to load README"
              description="Please try again later."
              type="error"
              showIcon
            />
          )}
          {!readmeLoading && !readmeError && !readme?.readme_html && (
            <Empty description="No README available" />
          )}
          {readme?.readme_html && (
            <XMarkdown content={readme.readme_html} openLinksInNewTab />
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
          <Tooltip title={isFetching ? 'Metadata is being fetched...' : undefined}>
            <Button
              icon={<ReloadOutlined />}
              loading={refreshLoading}
              disabled={isFetching}
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
          </Tooltip>
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

      {/* ── Inline fetching banner ─────────────────────────────────────────── */}
      {isFetching && (
        <Alert
          type="info"
          title="Metadata is being fetched in background..."
          description="Some fields may be incomplete. The page will update automatically when fetching completes."
          showIcon
        />
      )}

      {/* ── Tabs ────────────────────────────────────────────────────────────── */}
      <Card>
        <Tabs activeKey={activeTab} onChange={(key) => setActiveTab(key)} items={tabItems} />
      </Card>
    </Flex>
  );
};

export default RepositoryDetailPage;
