/**
 * @file Profile/MyProvidersCard.tsx
 * @description Card «My providers» личного кабинета: провайдеры, принадлежащие
 *              пользователю (owned) и расшаренные на его команды (shared).
 *              Деление — чистый client-side helper `splitMyProviders`.
 * @dependencies antd, react-router, RTK Query, StatusChip
 * @relatedFiles ./index.tsx, ./splitMyProviders.ts, ../../../store/api, ../../../types
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { Alert, Button, Card, Empty, Segmented, Spin, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useGetProvidersQuery } from '../../store/api';
import { StatusChip } from '../../components/StatusChip';
import { splitMyProviders } from './splitMyProviders';
import type { ResourceProvider } from '../../types';

interface MyProvidersCardProps {
  userId: number | undefined;
  myTeamIds: Set<number>;
}

type ProviderFilter = 'all' | 'owned' | 'shared';

const DOMAIN_LABELS: Record<string, string> = {
  git: 'Git',
  docker: 'Docker',
  helm: 'Helm',
};

export function MyProvidersCard({ userId, myTeamIds }: MyProvidersCardProps) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<ProviderFilter>('all');
  const { data: providers = [], isLoading, isError } = useGetProvidersQuery();

  const { owned, shared } = useMemo(
    () => splitMyProviders(providers, userId, myTeamIds),
    [providers, userId, myTeamIds]
  );

  const visibleProviders = useMemo(() => {
    if (filter === 'owned') return owned;
    if (filter === 'shared') return shared;
    return [...owned, ...shared];
  }, [filter, owned, shared]);

  const columns: ColumnsType<ResourceProvider> = [
    {
      title: 'Name',
      key: 'name',
      render: (_: unknown, record) => (
        <Typography.Text strong>{record.label || record.name}</Typography.Text>
      ),
    },
    {
      title: 'Type',
      key: 'type',
      render: (_: unknown, record) => (
        <span>
          <Tag>{DOMAIN_LABELS[record.domain] ?? record.domain}</Tag>
          <Tag>{record.subtype}</Tag>
        </span>
      ),
    },
    {
      title: 'Access',
      key: 'access',
      render: (_: unknown, record) => {
        if (record.owner_user_id === userId) {
          return <Tag color="blue">Owned</Tag>;
        }
        return <Tag color="cyan">Shared: {record.team_name ?? record.team_id}</Tag>;
      },
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record) => (
        <StatusChip status={record.status_flag} statusText={record.status_text} />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: () => (
        <Button type="link" onClick={() => navigate('/settings/providers')}>
          Manage
        </Button>
      ),
    },
  ];

  if (isLoading) {
    return (
      <Card title="My providers">
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card title="My providers">
        <Alert title="Failed to load providers" type="error" showIcon />
      </Card>
    );
  }

  return (
    <Card
      title="My providers"
      extra={
        <Segmented<ProviderFilter>
          value={filter}
          onChange={setFilter}
          options={[
            { label: 'All', value: 'all' },
            { label: 'Owned', value: 'owned' },
            { label: 'Shared with teams', value: 'shared' },
          ]}
        />
      }
    >
      <Table<ResourceProvider>
        columns={columns}
        dataSource={visibleProviders}
        rowKey="id"
        pagination={false}
        scroll={{ x: 640 }}
        locale={{
          emptyText:
            filter === 'owned' ? (
              <Empty description="You don't own any providers" />
            ) : filter === 'shared' ? (
              <Empty description="No providers are shared with your teams" />
            ) : (
              <Empty description="You don't have any providers" />
            ),
        }}
      />
    </Card>
  );
}
