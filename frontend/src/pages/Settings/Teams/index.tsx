/**
 * @file Settings/Teams/index.tsx
 * @description "My teams" page (`/settings/teams`): teams where the caller is a member.
 *              Lead sees invite/remove controls; regular member is read-only.
 * @dependencies antd, RTK Query
 * @relatedFiles ../../../store/api.ts, ../../../types/index.ts
 */

import { Alert, Card, Empty, Flex, Spin, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useGetTeamsQuery } from '../../../store/api';
import type { Team } from '../../../types';

export function SettingsTeams() {
  const { data: teams = [], isLoading, isError } = useGetTeamsQuery();

  const columns: ColumnsType<Team> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    { title: 'Description', dataIndex: 'description', key: 'description' },
    {
      title: 'Lead',
      key: 'lead',
      render: (_: unknown, record) => <Typography.Text>{record.owner.username}</Typography.Text>,
    },
    {
      title: 'My role',
      dataIndex: 'my_role',
      key: 'my_role',
      render: (role: string | null) =>
        role === 'lead' ? <Tag color="gold">Lead</Tag> : <Tag>Member</Tag>,
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Flex vertical gap={4}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          My teams
        </Typography.Title>
        <Typography.Text type="secondary">
          Teams you participate in. Leads can manage members from the admin panel.
        </Typography.Text>
      </Flex>

      {isLoading ? (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      ) : isError ? (
        <Alert title="Failed to load teams" type="error" showIcon />
      ) : (
        <Card>
          <Table
            columns={columns}
            dataSource={teams as Team[]}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: <Empty description="You are not a member of any team" /> }}
          />
        </Card>
      )}
    </Flex>
  );
}

export default SettingsTeams;
