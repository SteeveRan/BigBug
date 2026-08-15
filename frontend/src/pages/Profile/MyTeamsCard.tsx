/**
 * @file Profile/MyTeamsCard.tsx
 * @description Card «My teams» личного кабинета: список команд, где пользователь
 *              состоит, с раскрытием состава (members) через ленивую загрузку.
 * @dependencies antd, RTK Query
 * @relatedFiles ./index.tsx, ../../../store/api, ../../../types
 */

import { Alert, Card, Empty, Spin, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useGetTeamMembersQuery } from '../../store/api';
import type { Team, TeamMember } from '../../types';

interface MyTeamsCardProps {
  teams: Team[];
  isLoading: boolean;
  isError: boolean;
}

/** Рендер роли пользователя в команде: gold=Lead, default=Member. */
function renderRole(role: Team['my_role']) {
  return role === 'lead' ? <Tag color="gold">Lead</Tag> : <Tag>Member</Tag>;
}

/** Состав команды: username, роль, дата вступления. */
function TeamMembers({ teamId }: { teamId: number }) {
  const { data: members = [], isLoading, isError } = useGetTeamMembersQuery(teamId);

  if (isLoading) {
    return (
      <div style={{ padding: 16 }}>
        <Spin size="small" />
      </div>
    );
  }

  if (isError) {
    return (
      <div style={{ padding: 16 }}>
        <Alert title="Failed to load team members" type="error" showIcon />
      </div>
    );
  }

  if (members.length === 0) {
    return (
      <div style={{ padding: 16 }}>
        <Empty description="No members" />
      </div>
    );
  }

  const memberColumns: ColumnsType<TeamMember> = [
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
      render: (username: string) => <Typography.Text strong>{username}</Typography.Text>,
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (role: TeamMember['role']) =>
        role === 'lead' ? <Tag color="gold">Lead</Tag> : <Tag>Member</Tag>,
    },
    {
      title: 'Joined',
      dataIndex: 'joined_at',
      key: 'joined_at',
      render: (joinedAt: string) =>
        new Date(joinedAt).toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        }),
    },
  ];

  return (
    <Table<TeamMember>
      columns={memberColumns}
      dataSource={members}
      rowKey="user_id"
      pagination={false}
      size="small"
    />
  );
}

const columns: ColumnsType<Team> = [
  {
    title: 'Name',
    dataIndex: 'name',
    key: 'name',
    render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
  },
  {
    title: 'Description',
    dataIndex: 'description',
    key: 'description',
    render: (description: string | null) => (
      <Typography.Text type="secondary">{description ?? '—'}</Typography.Text>
    ),
  },
  {
    title: 'Lead',
    key: 'lead',
    render: (_: unknown, record) => <Typography.Text>{record.owner.username}</Typography.Text>,
  },
  {
    title: 'My role',
    dataIndex: 'my_role',
    key: 'my_role',
    render: renderRole,
  },
  {
    title: 'Members',
    dataIndex: 'members_count',
    key: 'members_count',
    width: 100,
  },
];

export function MyTeamsCard({ teams, isLoading, isError }: MyTeamsCardProps) {
  return (
    <Card title="My teams">
      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : isError ? (
        <Alert title="Failed to load teams" type="error" showIcon />
      ) : (
        <Table<Team>
          columns={columns}
          dataSource={teams}
          rowKey="id"
          pagination={false}
          scroll={{ x: 640 }}
          locale={{
            emptyText: <Empty description="You are not a member of any team" />,
          }}
          expandable={{
            expandedRowRender: (record) => <TeamMembers teamId={record.id} />,
          }}
        />
      )}
    </Card>
  );
}
