/**
 * @file Orphaned/RelinkModal.tsx
 * @description Модальное окно для восстановления orphaned зеркала — Reassign, Move Target, Delete
 * @dependencies antd, @ant-design/icons, RTK Query
 */

import { useState, useEffect } from 'react';
import {
  Modal,
  Tabs,
  Typography,
  Select,
  Input,
  Button,
  Alert,
  Flex,
  Descriptions,
  Tag,
  Divider,
  App,
} from 'antd';
import { SwapOutlined, LinkOutlined, DeleteOutlined } from '@ant-design/icons';
import {
  useReassignOrphanedMirrorMutation,
  useMoveOrphanedTargetMutation,
  useDeleteOrphanedMirrorMutation,
  useGetSyncGroupsQuery,
} from '../../../store/api';
import type { OrphanedMirror, OrphanReason, SyncGroup } from '../../../types';

export interface RelinkModalProps {
  mirror: OrphanedMirror;
  open: boolean;
  onClose: () => void;
}

const ORPHAN_REASON_COLORS: Record<OrphanReason, string> = {
  provider_deleted: 'red',
  credentials_invalid: 'orange',
  source_not_found: 'yellow',
  target_manual_delete: 'magenta',
};

export const RelinkModal = ({ mirror, open, onClose }: RelinkModalProps) => {
  const { message } = App.useApp();
  const { data: syncGroupsData = [] } = useGetSyncGroupsQuery();

  const [activeTab, setActiveTab] = useState<string>('reassign');

  // Reassign tab state
  const [selectedSyncGroupId, setSelectedSyncGroupId] = useState<number | undefined>(undefined);
  const [reassign, { isLoading: isReassigning }] = useReassignOrphanedMirrorMutation();

  // Move target tab state
  const [newTargetPath, setNewTargetPath] = useState(mirror.target_path);
  const [moveTarget, { isLoading: isMoving }] = useMoveOrphanedTargetMutation();

  // Delete tab
  const [deleteMirror, { isLoading: isDeleting }] = useDeleteOrphanedMirrorMutation();

  // Reset state when mirror changes
  useEffect(() => {
    if (mirror) {
      setNewTargetPath(mirror.target_path);
      setSelectedSyncGroupId(undefined);
      setActiveTab('reassign');
    }
  }, [mirror]);

  const handleReassign = async () => {
    if (!selectedSyncGroupId) return;
    try {
      await reassign({
        mirrorId: mirror.mirror_id,
        syncGroupId: selectedSyncGroupId,
      }).unwrap();
      message.success(`Mirror "${mirror.mirror_name}" reassigned to sync group`);
      onClose();
    } catch {
      message.error('Failed to reassign mirror');
    }
  };

  const handleMoveTarget = async () => {
    if (!newTargetPath.trim()) return;
    try {
      await moveTarget({
        mirrorId: mirror.mirror_id,
        targetPath: newTargetPath.trim(),
      }).unwrap();
      message.success(`Target path updated for "${mirror.mirror_name}"`);
      onClose();
    } catch {
      message.error('Failed to update target path');
    }
  };

  const handleDelete = async () => {
    try {
      await deleteMirror(mirror.mirror_id).unwrap();
      message.success(`Mirror "${mirror.mirror_name}" deleted`);
      onClose();
    } catch {
      message.error('Failed to delete mirror');
    }
  };

  const syncGroupOptions = (syncGroupsData as SyncGroup[]).map((sg: SyncGroup) => ({
    label: sg.name,
    value: sg.id,
  }));

  const tabItems = [
    {
      key: 'reassign',
      label: (
        <span>
          <LinkOutlined /> Reassign
        </span>
      ),
      children: (
        <Flex vertical gap={16}>
          <Typography.Text type="secondary">
            Move this mirror to a different sync group. The target path will be preserved.
          </Typography.Text>
          <Select
            placeholder="Select Sync Group…"
            style={{ width: '100%' }}
            value={selectedSyncGroupId}
            onChange={setSelectedSyncGroupId}
            options={syncGroupOptions}
            showSearch
            optionFilterProp="label"
          />
          <Button
            type="primary"
            icon={<LinkOutlined />}
            loading={isReassigning}
            disabled={!selectedSyncGroupId}
            onClick={handleReassign}
          >
            Reassign to Sync Group
          </Button>
        </Flex>
      ),
    },
    {
      key: 'move-target',
      label: (
        <span>
          <SwapOutlined /> Move Target
        </span>
      ),
      children: (
        <Flex vertical gap={16}>
          <Typography.Text type="secondary">
            Change the GitLab target project path for this mirror.
          </Typography.Text>
          <Input
            placeholder="New target path (e.g., org/group/project)"
            value={newTargetPath}
            onChange={(e) => setNewTargetPath(e.target.value)}
          />
          <Button
            type="primary"
            icon={<SwapOutlined />}
            loading={isMoving}
            disabled={!newTargetPath.trim() || newTargetPath.trim() === mirror.target_path}
            onClick={handleMoveTarget}
          >
            Update Target Path
          </Button>
        </Flex>
      ),
    },
    {
      key: 'delete',
      label: (
        <span>
          <DeleteOutlined /> Delete
        </span>
      ),
      children: (
        <Flex vertical gap={16}>
          <Alert
            type="warning"
            message="This will soft-delete the mirror. It can be restored within 30 days."
            showIcon
          />
          <Button
            danger
            type="primary"
            icon={<DeleteOutlined />}
            loading={isDeleting}
            onClick={handleDelete}
          >
            Delete Mirror
          </Button>
        </Flex>
      ),
    },
  ];

  return (
    <Modal
      title={
        <Typography.Text strong style={{ fontSize: 16 }}>
          Re-link: {mirror.mirror_name}
        </Typography.Text>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={560}
      destroyOnHidden
    >
      <Flex vertical gap={16}>
        {/* Mirror Info */}
        <Descriptions column={2} size="small" bordered>
          <Descriptions.Item label="Mirror Name">{mirror.mirror_name}</Descriptions.Item>
          <Descriptions.Item label="Source URL">
            <Typography.Text copyable ellipsis style={{ maxWidth: 180 }}>
              {mirror.source_url}
            </Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Target Path">
            <Typography.Text code>{mirror.target_path}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Orphan Reason">
            <Tag color={ORPHAN_REASON_COLORS[mirror.orphan_reason]}>
              {mirror.orphan_reason_text}
            </Tag>
          </Descriptions.Item>
        </Descriptions>

        <Divider style={{ margin: '4px 0' }} />

        {/* Tabs */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          size="small"
        />
      </Flex>
    </Modal>
  );
};
