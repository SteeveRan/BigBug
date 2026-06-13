/**
 * @file MirrorDetail.tsx
 * @description Детальная страница GitLab зеркала: метаданные, расписание синхронизации, история синхронизаций
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Flex,
  Switch,
  Descriptions,
  Table,
  Input,
  Spin,
  Space,
} from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined, LinkOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  useGetMirrorQuery,
  useGetMirrorLogsQuery,
  useGetMirrorScheduleQuery,
  useUpdateMirrorScheduleMutation,
  useTriggerSyncMutation,
} from '../../store/api';
import { GitlabMirror, SyncLog, SyncSchedule } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function MirrorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const mirrorId = Number(id);

  const { data: mirror, isLoading } = useGetMirrorQuery(mirrorId);
  const { data: logs = [] } = useGetMirrorLogsQuery(mirrorId);
  const { data: schedule } = useGetMirrorScheduleQuery(mirrorId);
  const [updateSchedule] = useUpdateMirrorScheduleMutation();
  const [triggerSync, { isLoading: syncing }] = useTriggerSyncMutation();

  const [cronExpr, setCronExpr] = useState('');

  const m = mirror as GitlabMirror | undefined;
  const s = schedule as SyncSchedule | undefined;

  const handleToggleEnabled = async () => {
    if (!s) return;
    await updateSchedule({ id: mirrorId, data: { is_enabled: !s.is_enabled } });
  };

  const handleToggleDefault = async () => {
    if (!s) return;
    await updateSchedule({ id: mirrorId, data: { use_default_schedule: !s.use_default_schedule } });
  };

  const handleSaveCron = async () => {
    await updateSchedule({
      id: mirrorId,
      data: { cron_expression: cronExpr, use_default_schedule: false },
    });
  };

  const logColumns: ColumnsType<SyncLog> = [
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: 'Triggered By',
      dataIndex: 'triggered_by',
      key: 'triggered_by',
      render: (val: string | null) => val ?? '—',
    },
    {
      title: 'Pipeline',
      key: 'pipeline',
      render: (_: unknown, record: SyncLog) =>
        record.pipeline_url ? (
          <Button size="small" type="link" href={record.pipeline_url} target="_blank">
            #{record.pipeline_id}
          </Button>
        ) : (
          (record.pipeline_id ?? '—')
        ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: SyncLog) => (
        <StatusChip
          statusFlag={record.status_flag as 0 | 1 | 2 | 3 | 4}
          statusText={record.status_text}
        />
      ),
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: unknown, record: SyncLog) =>
        record.started_at && record.finished_at
          ? `${Math.round((new Date(record.finished_at).getTime() - new Date(record.started_at).getTime()) / 1000)}s`
          : '—',
    },
  ];

  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: 48 }}>
        <Spin size="large" />
      </Flex>
    );
  }
  if (!m) return <Typography.Title level={5}>Mirror not found</Typography.Title>;

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex align="center" gap={12} wrap="wrap">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/mirrors')}>
          Back to Mirrors
        </Button>
        <Typography.Title level={4} style={{ margin: 0, flex: 1 }}>
          {m.gitlab_name ?? m.gitlab_url}
        </Typography.Title>
        <Space>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={syncing}
            onClick={() => triggerSync(mirrorId)}
          >
            Sync Now
          </Button>
          <Button
            icon={<LinkOutlined />}
            href={m.gitlab_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            GitLab
          </Button>
        </Space>
      </Flex>

      {/* ── Info & Schedule Cards ───────────────────────────────────────────── */}
      <Flex gap={16} wrap="wrap">
        <Card title="Mirror Info" style={{ flex: '1 1 300px' }}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Status">
              <StatusChip
                statusFlag={m.status_flag as 0 | 1 | 2 | 3 | 4}
                statusText={m.status_text}
              />
            </Descriptions.Item>
            <Descriptions.Item label="Branch">{m.mirrored_branch}</Descriptions.Item>
            <Descriptions.Item label="Last Sync">
              {m.last_sync_at ? new Date(m.last_sync_at).toLocaleString() : 'Never'}
            </Descriptions.Item>
            <Descriptions.Item label="Last Synced Release">
              {m.last_synced_release_tag ?? '—'}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {s && (
          <Card title="Schedule" style={{ flex: '1 1 300px' }}>
            <Flex vertical gap={12}>
              <Flex align="center" justify="space-between">
                <Typography.Text>Enable scheduled sync</Typography.Text>
                <Switch checked={s.is_enabled} onChange={handleToggleEnabled} />
              </Flex>
              <Flex align="center" justify="space-between">
                <Typography.Text>Use default schedule</Typography.Text>
                <Switch
                  checked={s.use_default_schedule}
                  onChange={handleToggleDefault}
                  disabled={!s.is_enabled}
                />
              </Flex>
              {!s.use_default_schedule && s.is_enabled && (
                <Space.Compact style={{ width: '100%' }}>
                  <Input
                    value={cronExpr || s.cron_expression || ''}
                    onChange={(e) => setCronExpr(e.target.value)}
                    placeholder="0 2 * * *"
                  />
                  <Button onClick={handleSaveCron}>Save</Button>
                </Space.Compact>
              )}
              {s.last_run_at && (
                <Typography.Text type="secondary">
                  Last run: {new Date(s.last_run_at).toLocaleString()}
                </Typography.Text>
              )}
            </Flex>
          </Card>
        )}
      </Flex>

      {/* ── Sync History Table ───────────────────────────────────────────────── */}
      <Card title="Sync History">
        <Table
          columns={logColumns}
          dataSource={logs as SyncLog[]}
          rowKey="id"
          size="small"
          pagination={false}
          locale={{ emptyText: 'No sync history yet' }}
        />
      </Card>
    </Flex>
  );
}
