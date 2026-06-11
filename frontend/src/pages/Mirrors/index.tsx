/**
 * @file index.tsx
 * @description Страница списка GitLab зеркал: таблица с columns/dataSource, модальное окно импорта
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Modal,
  Input,
  App,
  Tooltip,
  Space,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import {
  useListMirrorsQuery,
  useImportMirrorMutation,
  useTriggerSyncMutation,
} from '../../store/api';
import { GitlabMirror } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function MirrorsPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { data: mirrors = [], isLoading } = useListMirrorsQuery();
  const [importMirror] = useImportMirrorMutation();
  const [triggerSync] = useTriggerSyncMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [githubUrl, setGithubUrl] = useState('');
  const [gitlabUrl, setGitlabUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleImport = async () => {
    setSubmitting(true);
    try {
      await importMirror({ github_url: githubUrl, gitlab_url: gitlabUrl }).unwrap();
      message.success('Mirror imported successfully');
      setDialogOpen(false);
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenDialog = () => {
    setGithubUrl('');
    setGitlabUrl('');
    setDialogOpen(true);
  };

  const columns: ColumnsType<GitlabMirror> = [
    {
      title: 'GitLab Project',
      key: 'project',
      render: (_: unknown, record: GitlabMirror) => (
        <Flex vertical>
          <Typography.Link onClick={() => navigate(`/mirrors/${record.id}`)}>
            {record.gitlab_name ?? record.gitlab_url}
          </Typography.Link>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.gitlab_namespace}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Branch',
      dataIndex: 'mirrored_branch',
      key: 'branch',
    },
    {
      title: 'Last Sync',
      dataIndex: 'last_sync_at',
      key: 'last_sync_at',
      render: (val: string | null) =>
        val ? new Date(val).toLocaleString() : '—',
    },
    {
      title: 'Last Release Tag',
      dataIndex: 'last_synced_release_tag',
      key: 'last_synced_release_tag',
      render: (val: string | null) => val ?? '—',
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: GitlabMirror) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      render: (_: unknown, record: GitlabMirror) => (
        <Tooltip title="Trigger sync now">
          <Button
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              triggerSync(record.id);
            }}
          />
        </Tooltip>
      ),
    },
  ];

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          GitLab Mirrors
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenDialog}>
          Import Mirror
        </Button>
      </Flex>

      {/* ── Table ───────────────────────────────────────────────────────────── */}
      <Card>
        <Table
          columns={columns}
          dataSource={mirrors as GitlabMirror[]}
          rowKey="id"
          loading={isLoading}
          onRow={(record) => ({
            onClick: () => navigate(`/mirrors/${record.id}`),
            style: { cursor: 'pointer' },
          })}
          pagination={false}
          locale={{ emptyText: 'No mirrors yet. Import a mirror to get started.' }}
        />
      </Card>

      {/* ── Import Modal ────────────────────────────────────────────────────── */}
      <Modal
        title="Import Mirror"
        open={dialogOpen}
        onOk={handleImport}
        onCancel={() => setDialogOpen(false)}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !githubUrl || !gitlabUrl }}
        okText="Import"
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="https://github.com/owner/repo"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
          />
          <Input
            placeholder="https://gitlab.example.com/namespace/repo"
            value={gitlabUrl}
            onChange={(e) => setGitlabUrl(e.target.value)}
          />
        </Space>
      </Modal>
    </Flex>
  );
}
