/**
 * @file Admin/Teams/index.tsx
 * @description Admin teams management (`/admin/teams`): CRUD all teams with lead selection.
 * @dependencies antd, RTK Query, PermissionGate
 * @relatedFiles ./TeamDetail/index.tsx, ../../../store/api.ts
 */

import { useState } from 'react';
import {
  App,
  Alert,
  Button,
  Card,
  Empty,
  Flex,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { Link } from 'react-router';
import {
  useGetTeamsQuery,
  useCreateTeamMutation,
  useUpdateTeamMutation,
  useDeleteTeamMutation,
  useListUsersQuery,
} from '../../../store/api';
import type { Team, TeamCreate, User } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';

interface TeamFormValues {
  name: string;
  description?: string;
  owner_user_id: number;
}

function TeamModal({ open, team, onClose }: { open: boolean; team?: Team; onClose: () => void }) {
  const { message } = App.useApp();
  const [form] = Form.useForm<TeamFormValues>();
  const isEdit = !!team;
  const { data: users = [] } = useListUsersQuery();
  const [createTeam, { isLoading: isCreating }] = useCreateTeamMutation();
  const [updateTeam, { isLoading: isUpdating }] = useUpdateTeamMutation();
  const isLoading = isCreating || isUpdating;

  const handleSubmit = async (values: TeamFormValues) => {
    try {
      if (isEdit && team) {
        await updateTeam({
          id: team.id,
          data: {
            name: values.name,
            description: values.description,
            owner_user_id: values.owner_user_id,
          },
        }).unwrap();
        message.success('Team updated');
      } else {
        const data: TeamCreate = {
          name: values.name,
          description: values.description,
          owner_user_id: values.owner_user_id,
        };
        await createTeam(data).unwrap();
        message.success('Team created');
      }
      onClose();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to save team');
    }
  };

  return (
    <Modal
      title={isEdit ? `Edit team: ${team?.name}` : 'Create team'}
      open={open}
      onCancel={onClose}
      destroyOnHidden
      footer={[
        <Button key="cancel" onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>,
        <Button key="save" type="primary" loading={isLoading} onClick={() => form.submit()}>
          {isEdit ? 'Save' : 'Create'}
        </Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          name: team?.name,
          description: team?.description ?? undefined,
          owner_user_id: team?.owner.id,
        }}
      >
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input placeholder="e.g. platform" />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="owner_user_id" label="Lead (owner)" rules={[{ required: true }]}>
          <Select
            showSearch
            optionFilterProp="label"
            options={users.map((u) => {
              const user = u as User;
              return { label: user.username, value: user.id };
            })}
            placeholder="Select lead"
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export function AdminTeams() {
  const { message } = App.useApp();
  const { data: teams = [], isLoading, isError } = useGetTeamsQuery();
  const [deleteTeam] = useDeleteTeamMutation();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Team | undefined>(undefined);

  const handleDelete = async (id: number, name: string) => {
    try {
      await deleteTeam(id).unwrap();
      message.success(`Team "${name}" deleted`);
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to delete team');
    }
  };

  const columns: ColumnsType<Team> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record) => (
        <Link to={`/admin/teams/${record.id}`}>
          <Typography.Text strong>{name}</Typography.Text>
        </Link>
      ),
    },
    {
      title: 'Lead',
      key: 'lead',
      render: (_: unknown, record) => <Typography.Text>{record.owner.username}</Typography.Text>,
    },
    {
      title: 'Members',
      dataIndex: 'members_count',
      key: 'members_count',
      width: 100,
      align: 'center',
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 140,
      render: (_: unknown, record) => (
        <Space size={4}>
          <PermissionGate permission="teams:write">
            <Button
              size="small"
              type="text"
              icon={<EditOutlined />}
              onClick={() => {
                setEditing(record);
                setModalOpen(true);
              }}
            />
            <Popconfirm
              title="Delete team?"
              description="Team providers will be unshared."
              onConfirm={() => handleDelete(record.id, record.name)}
            >
              <Button size="small" type="text" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Flex vertical gap={4}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Teams
          </Typography.Title>
          <Typography.Text type="secondary">
            Manage teams and their leads for provider sharing.
          </Typography.Text>
        </Flex>
        <PermissionGate permission="teams:write">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(undefined);
              setModalOpen(true);
            }}
          >
            Create team
          </Button>
        </PermissionGate>
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
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="No teams configured" /> }}
          />
        </Card>
      )}

      <TeamModal
        open={modalOpen}
        team={editing}
        onClose={() => {
          setModalOpen(false);
          setEditing(undefined);
        }}
      />
    </Flex>
  );
}

export default AdminTeams;
