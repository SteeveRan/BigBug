/**
 * @file Admin/Credentials/index.tsx
 * @description Pure credentials management page (`/admin/credentials`): CRUD + test.
 * @dependencies antd, RTK Query, PermissionGate, StatusChip
 * @relatedFiles ../../../store/api.ts, ../../../types/index.ts
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
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import {
  useGetCredentialsQuery,
  useCreateCredentialMutation,
  useUpdateCredentialMutation,
  useDeleteCredentialMutation,
  useTestCredentialMutation,
} from '../../../store/api';
import type { CredentialDetail, CredentialType } from '../../../types';
import { StatusChip } from '../../../components/StatusChip';
import { PermissionGate } from '../../../components/PermissionGate';

const CREDENTIAL_TYPE_OPTIONS: { label: string; value: CredentialType }[] = [
  { label: 'GitHub Token', value: 'github_token' },
  { label: 'GitLab Token', value: 'gitlab_token' },
  { label: 'HTTPS Basic', value: 'https_basic' },
  { label: 'SSH Key', value: 'ssh_key' },
];

interface CredentialFormValues {
  name: string;
  credential_type: CredentialType;
  provider: string;
  username?: string;
  secret: string;
  ssh_public_key?: string;
  base_url?: string;
}

function CredentialModal({
  open,
  credential,
  onClose,
}: {
  open: boolean;
  credential?: CredentialDetail;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<CredentialFormValues>();
  const isEdit = !!credential;
  const [createCredential, { isLoading: isCreating }] = useCreateCredentialMutation();
  const [updateCredential, { isLoading: isUpdating }] = useUpdateCredentialMutation();
  const isLoading = isCreating || isUpdating;
  const credentialType = Form.useWatch('credential_type', form);

  const handleSubmit = async (values: CredentialFormValues) => {
    try {
      if (isEdit && credential) {
        await updateCredential({
          id: credential.id,
          data: {
            name: values.name,
            username: values.username,
            secret: values.secret || undefined,
            ssh_public_key: values.ssh_public_key,
            base_url: values.base_url,
          },
        }).unwrap();
        message.success('Credential updated');
      } else {
        await createCredential(values).unwrap();
        message.success('Credential created');
      }
      onClose();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Failed to save credential');
    }
  };

  return (
    <Modal
      title={isEdit ? `Edit credential: ${credential?.name}` : 'Create credential'}
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
          credential_type: credential?.credential_type ?? 'github_token',
          provider: credential?.provider ?? 'github',
        }}
      >
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input placeholder="e.g. my-github-token" />
        </Form.Item>
        <Form.Item name="credential_type" label="Type" rules={[{ required: true }]}>
          <Select options={CREDENTIAL_TYPE_OPTIONS} />
        </Form.Item>
        <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
          <Input placeholder="github, gitlab, generic" />
        </Form.Item>
        {credentialType === 'https_basic' && (
          <Form.Item name="username" label="Username" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        )}
        <Form.Item
          name="secret"
          label={credentialType === 'ssh_key' ? 'Private key' : 'Secret'}
          rules={isEdit ? [] : [{ required: true }]}
        >
          <Input.TextArea rows={credentialType === 'ssh_key' ? 5 : 2} />
        </Form.Item>
        {credentialType === 'ssh_key' && (
          <Form.Item name="ssh_public_key" label="Public key">
            <Input.TextArea rows={3} />
          </Form.Item>
        )}
        <Form.Item name="base_url" label="Base URL">
          <Input placeholder="https://" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export function AdminCredentials() {
  const { message } = App.useApp();
  const { data: credentials = [], isLoading, isError } = useGetCredentialsQuery();
  const [deleteCredential] = useDeleteCredentialMutation();
  const [testCredential, { isLoading: isTesting }] = useTestCredentialMutation();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CredentialDetail | undefined>(undefined);

  const handleDelete = async (id: number, name: string) => {
    try {
      await deleteCredential(id).unwrap();
      message.success(`Credential "${name}" deleted`);
    } catch {
      message.error('Failed to delete credential');
    }
  };

  const handleTest = async (id: number) => {
    try {
      await testCredential(id).unwrap();
      message.success('Credential test passed');
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Credential test failed');
    }
  };

  const columns: ColumnsType<CredentialDetail> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record) => (
        <Flex vertical>
          <Typography.Text strong>{name}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.provider}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'credential_type',
      key: 'credential_type',
      render: (type: CredentialType) => <Typography.Text>{type}</Typography.Text>,
    },
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
      render: (username: string | null) => <Typography.Text>{username ?? '—'}</Typography.Text>,
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Last tested',
      dataIndex: 'last_tested_at',
      key: 'last_tested_at',
      render: (v: string | null) => <Typography.Text>{v ?? '—'}</Typography.Text>,
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 180,
      render: (_: unknown, record) => (
        <Space size={4}>
          <Button
            size="small"
            type="text"
            icon={<PlayCircleOutlined />}
            loading={isTesting}
            onClick={() => handleTest(record.id)}
          />
          <PermissionGate permission="credentials:write">
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
              title="Delete credential?"
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
            Credentials
          </Typography.Title>
          <Typography.Text type="secondary">
            Manage secrets (tokens, passwords, SSH keys) used by providers.
          </Typography.Text>
        </Flex>
        <PermissionGate permission="credentials:write">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(undefined);
              setModalOpen(true);
            }}
          >
            Create credential
          </Button>
        </PermissionGate>
      </Flex>

      {isLoading ? (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      ) : isError ? (
        <Alert title="Failed to load credentials" type="error" showIcon />
      ) : (
        <Card>
          <Table
            columns={columns}
            dataSource={credentials as CredentialDetail[]}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="No credentials configured" /> }}
          />
        </Card>
      )}

      <CredentialModal
        open={modalOpen}
        credential={editing}
        onClose={() => {
          setModalOpen(false);
          setEditing(undefined);
        }}
      />
    </Flex>
  );
}

export default AdminCredentials;
