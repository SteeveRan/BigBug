/**
 * @file Admin/Teams/TeamDetail/index.tsx
 * @description Team detail page: members table (invite/remove) + team providers tab.
 * @dependencies antd, RTK Query, react-router, PermissionGate
 * @relatedFiles ../index.tsx, ../../../../store/api.ts
 */

import { useState } from 'react';
import { App, Button, Card, Flex, Modal, Popconfirm, Select, Table, Tabs, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ArrowLeftOutlined, UserAddOutlined, DeleteOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router';
import {
  useGetTeamsQuery,
  useGetTeamMembersQuery,
  useAddTeamMemberMutation,
  useRemoveTeamMemberMutation,
  useGetTeamProvidersQuery,
  useListUsersQuery,
} from '../../../../store/api';
import type { Team, TeamMember, ResourceProvider, User } from '../../../../types';
import { PermissionGate } from '../../../../components/PermissionGate';

export function TeamDetailPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const navigate = useNavigate();
  const numericId = Number(teamId);

  const { data: teams = [] } = useGetTeamsQuery();
  const team = teams.find((t: Team) => t.id === numericId);

  const { data: members = [], isLoading: membersLoading } = useGetTeamMembersQuery(numericId, {
    skip: !numericId,
  });
  const { data: providers = [], isLoading: providersLoading } = useGetTeamProvidersQuery(
    numericId,
    { skip: !numericId }
  );

  return (
    <Flex vertical gap={16}>
      <Flex align="center" gap={8}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/teams')}>
          Back to Teams
        </Button>
      </Flex>

      <Card>
        <Flex vertical gap={4}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            Team: {team?.name ?? '…'}
          </Typography.Title>
          <Typography.Text type="secondary">
            {team?.description ?? 'No description provided'}
          </Typography.Text>
        </Flex>
      </Card>

      <Card>
        <Tabs
          defaultActiveKey="members"
          items={[
            {
              key: 'members',
              label: 'Members',
              children: (
                <MembersTab
                  teamId={numericId}
                  members={members as TeamMember[]}
                  loading={membersLoading}
                />
              ),
            },
            {
              key: 'providers',
              label: 'Providers',
              children: (
                <ProvidersTab
                  providers={providers as ResourceProvider[]}
                  loading={providersLoading}
                />
              ),
            },
          ]}
        />
      </Card>
    </Flex>
  );
}

function MembersTab({
  teamId,
  members,
  loading,
}: {
  teamId: number;
  members: TeamMember[];
  loading: boolean;
}) {
  const { message } = App.useApp();
  const { data: users = [] } = useListUsersQuery();
  const [addMember, { isLoading: isAdding }] = useAddTeamMemberMutation();
  const [removeMember] = useRemoveTeamMemberMutation();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteUserId, setInviteUserId] = useState<number | undefined>(undefined);

  const handleInvite = async () => {
    if (inviteUserId === undefined) return;
    try {
      await addMember({ teamId, data: { user_id: inviteUserId } }).unwrap();
      message.success('Member invited');
      setInviteOpen(false);
      setInviteUserId(undefined);
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to invite member');
    }
  };

  const handleRemove = async (userId: number) => {
    try {
      await removeMember({ teamId, userId }).unwrap();
      message.success('Member removed');
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to remove member');
    }
  };

  const columns: ColumnsType<TeamMember> = [
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
      render: (username: string) => <Typography.Text strong>{username}</Typography.Text>,
    },
    { title: 'Role', dataIndex: 'role', key: 'role', width: 120 },
    { title: 'Joined', dataIndex: 'joined_at', key: 'joined_at' },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 100,
      render: (_: unknown, record) => (
        <PermissionGate permission="teams:manage_members">
          <Popconfirm title="Remove member?" onConfirm={() => handleRemove(record.user_id)}>
            <Button size="small" type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </PermissionGate>
      ),
    },
  ];

  return (
    <Flex vertical gap={12}>
      <Flex justify="flex-end">
        <PermissionGate permission="teams:manage_members">
          <Button type="primary" icon={<UserAddOutlined />} onClick={() => setInviteOpen(true)}>
            Invite member
          </Button>
        </PermissionGate>
      </Flex>
      <Table
        columns={columns}
        dataSource={members}
        rowKey="user_id"
        loading={loading}
        pagination={false}
        size="small"
      />
      <Modal
        title="Invite member"
        open={inviteOpen}
        onCancel={() => setInviteOpen(false)}
        onOk={handleInvite}
        okButtonProps={{ loading: isAdding, disabled: inviteUserId === undefined }}
      >
        <Select
          style={{ width: '100%' }}
          placeholder="Select user"
          value={inviteUserId}
          onChange={setInviteUserId}
          showSearch
          optionFilterProp="label"
          options={users.map((u) => {
            const user = u as User;
            return { label: user.username, value: user.id };
          })}
        />
      </Modal>
    </Flex>
  );
}

function ProvidersTab({ providers, loading }: { providers: ResourceProvider[]; loading: boolean }) {
  return (
    <Table
      rowKey="id"
      loading={loading}
      dataSource={providers}
      pagination={false}
      size="small"
      columns={[
        { title: 'Label', dataIndex: 'label', key: 'label' },
        { title: 'Subtype', dataIndex: 'subtype', key: 'subtype' },
        { title: 'Domain', dataIndex: 'domain', key: 'domain' },
      ]}
      locale={{ emptyText: 'No providers shared with this team' }}
    />
  );
}

export default TeamDetailPage;
