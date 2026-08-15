/**
 * @file Settings/Providers/ProviderDetail.tsx
 * @description Detail page for a single unified resource provider
 *              (`/settings/providers/:providerId`). Shows a Breadcrumb
 *              (Providers / {domain} / {name}) plus a Descriptions card with the
 *              provider's full metadata. Follows the same conventions as the
 *              repository / docker-image detail pages.
 * @dependencies antd, @ant-design/icons, react-router, RTK Query, StatusChip
 * @relatedFiles ./index.tsx, ./providersColumns.ts
 */

import { useNavigate, useParams } from 'react-router';
import { Alert, Breadcrumb, Button, Card, Descriptions, Flex, Spin, Tag, Typography } from 'antd';
import { ArrowLeftOutlined, GlobalOutlined, LockOutlined } from '@ant-design/icons';
import { useGetProviderQuery } from '../../../store/api';
import type {
  ProviderCategory,
  ProviderDirection,
  ProviderDomain,
  ProviderVisibility,
  ResourceProvider,
} from '../../../types';
import { StatusChip } from '../../../components/StatusChip';

const DOMAIN_LABELS: Record<ProviderDomain, string> = {
  git: 'Git',
  docker: 'Docker',
  helm: 'Helm',
};

const DOMAIN_COLORS: Record<ProviderDomain, string> = {
  git: 'geekblue',
  docker: 'cyan',
  helm: 'purple',
};

const CATEGORY_LABELS: Record<ProviderCategory, string> = {
  system: 'System',
  public: 'Public',
  private: 'Private',
};

const CATEGORY_COLORS: Record<ProviderCategory, string> = {
  system: 'gold',
  public: 'green',
  private: 'default',
};

const DIRECTION_LABELS: Record<ProviderDirection, string> = {
  external: 'External',
  internal: 'Internal',
};

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function VisibilityTag({ visibility }: { visibility: ProviderVisibility }) {
  if (visibility === 'public') {
    return (
      <Tag icon={<GlobalOutlined />} color="green">
        Public
      </Tag>
    );
  }
  if (visibility === 'team') {
    return <Tag color="blue">Team</Tag>;
  }
  return (
    <Tag icon={<LockOutlined />} color="default">
      Private
    </Tag>
  );
}

export function ProviderDetailPage() {
  const { providerId } = useParams<{ providerId: string }>();
  const navigate = useNavigate();
  const id = Number(providerId);

  const {
    data: provider,
    isLoading,
    isError,
  } = useGetProviderQuery(id, { skip: Number.isNaN(id) });

  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: '48px 0' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  if (isError || !provider) {
    return (
      <Flex vertical gap={16}>
        <Alert
          type="error"
          title="Failed to load provider"
          description="Please check the provider ID and try again."
          showIcon
        />
        <Flex>
          <Card>
            <Typography.Text type="secondary">
              Provider not found or you do not have access to it.
            </Typography.Text>
          </Card>
        </Flex>
      </Flex>
    );
  }

  const p: ResourceProvider = provider;

  return (
    <Flex vertical gap={16}>
      {/* ── Breadcrumb ─────────────────────────────────────────────────────── */}
      <Breadcrumb
        items={[
          { title: 'Providers', onClick: () => navigate('/settings/providers') },
          { title: DOMAIN_LABELS[p.domain] },
          { title: p.name },
        ]}
        itemRender={(route, _params, routes) => {
          const last = routes.indexOf(route) === routes.length - 1;
          if (last) return <span>{route.title}</span>;
          return (
            <a
              onClick={(e) => {
                e.preventDefault();
                (route.onClick as ((e: React.MouseEvent) => void) | undefined)?.(e);
              }}
            >
              {route.title}
            </a>
          );
        }}
      />

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <Flex align="center" gap={12} wrap="wrap">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/settings/providers')}>
          Back
        </Button>
        <Typography.Title level={4} style={{ margin: 0, flex: 1 }}>
          {p.label}
        </Typography.Title>
        <VisibilityTag visibility={p.visibility} />
        {p.is_default && <Tag color="blue">Default</Tag>}
        {p.is_protected && <Tag color="gold">Protected</Tag>}
      </Flex>

      {/* ── Detail info ────────────────────────────────────────────────────── */}
      <Card title="Provider Info">
        <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
          <Descriptions.Item label="Name">
            <Typography.Text strong>{p.name}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Label">{p.label}</Descriptions.Item>
          <Descriptions.Item label="Description">{p.description ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="Domain">
            <Tag color={DOMAIN_COLORS[p.domain]}>{DOMAIN_LABELS[p.domain]}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Subtype">
            <Typography.Text code>{p.subtype}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Category">
            <Tag color={CATEGORY_COLORS[p.category]}>{CATEGORY_LABELS[p.category]}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Direction">{DIRECTION_LABELS[p.direction]}</Descriptions.Item>
          <Descriptions.Item label="Base URL">
            {p.base_url ? (
              <Typography.Text code style={{ wordBreak: 'break-all' }}>
                {p.base_url}
              </Typography.Text>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Status">
            <StatusChip
              statusFlag={p.status_flag as 0 | 1 | 2 | 3 | 4}
              statusText={p.status_text}
            />
          </Descriptions.Item>
          <Descriptions.Item label="Active">
            {p.is_active ? <Tag color="success">Yes</Tag> : <Tag color="default">No</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="Verify SSL">{p.verify_ssl ? 'Yes' : 'No'}</Descriptions.Item>
          <Descriptions.Item label="Priority">{p.priority}</Descriptions.Item>
          <Descriptions.Item label="Created">{formatDate(p.created_at)}</Descriptions.Item>
          <Descriptions.Item label="Updated">{formatDate(p.updated_at)}</Descriptions.Item>
          <Descriptions.Item label="Last Checked">
            {formatDate(p.last_checked_at)}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </Flex>
  );
}

export default ProviderDetailPage;
