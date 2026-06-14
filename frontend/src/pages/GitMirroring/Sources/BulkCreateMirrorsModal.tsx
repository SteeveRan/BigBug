/**
 * @file BulkCreateMirrorsModal.tsx
 * @description Модалка массового создания зеркал — чекбоксы по репозиториям
 * @dependencies antd, RTK Query
 */

import { useEffect, useState, useMemo } from 'react';
import { Modal, Form, Select, Input, App, Typography, Checkbox, List, Spin, Empty } from 'antd';
import {
  useBulkCreateMirrorsMutation,
  useGetSourceRepositoriesQuery,
  useGetSyncGroupsQuery,
} from '../../../store/api';
import type { SourceRepository } from '../../../types';

interface BulkCreateMirrorsModalProps {
  open: boolean;
  onClose: () => void;
  /** Preselected source group id (0 = all groups) */
  groupId?: number;
}

interface FormValues {
  source_repository_ids: number[];
  default_target_namespace: string;
  sync_group_id: number;
}

export function BulkCreateMirrorsModal({ open, onClose, groupId }: BulkCreateMirrorsModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const [selectedRepoIds, setSelectedRepoIds] = useState<number[]>([]);
  const [search, setSearch] = useState('');

  const [bulkCreate, { isLoading }] = useBulkCreateMirrorsMutation();

  // Fetch source repositories
  const { data: repositories = [], isLoading: reposLoading } = useGetSourceRepositoriesQuery(
    { group_id: groupId ?? 0 },
    { skip: !open }
  );

  // Fetch sync groups
  const { data: syncGroups = [], isLoading: sgLoading } = useGetSyncGroupsQuery(undefined, {
    skip: !open,
  });

  // Filter by search
  const filteredRepos = useMemo(() => {
    if (!search.trim()) return repositories;
    const term = search.toLowerCase();
    return repositories.filter(
      (r) =>
        r.name.toLowerCase().includes(term) ||
        r.full_name.toLowerCase().includes(term)
    );
  }, [repositories, search]);

  // Reset on open
  useEffect(() => {
    if (open) {
      form.resetFields();
      setSelectedRepoIds([]);
      setSearch('');
    }
  }, [open, form]);

  const handleSubmit = async (values: FormValues) => {
    if (selectedRepoIds.length === 0) {
      message.warning('Select at least one repository');
      return;
    }
    try {
      const mirrors = selectedRepoIds.map((id) => {
        const repo = repositories.find((r) => r.id === id);
        return {
          source_repository_id: id,
          target_namespace: values.default_target_namespace,
          target_project_name: repo?.name || `repo-${id}`,
          sync_group_id: values.sync_group_id,
        };
      });
      await bulkCreate({
        mirrors,
        default_sync_group_id: values.sync_group_id,
        default_target_namespace: values.default_target_namespace,
      }).unwrap();
      message.success(`${mirrors.length} mirror(s) created successfully`);
      onClose();
    } catch {
      // error handled by RTK Query
    }
  };

  const toggleRepo = (id: number) => {
    setSelectedRepoIds((prev) =>
      prev.includes(id) ? prev.filter((rid) => rid !== id) : [...prev, id]
    );
  };

  const toggleAll = () => {
    if (selectedRepoIds.length === filteredRepos.length) {
      setSelectedRepoIds([]);
    } else {
      setSelectedRepoIds(filteredRepos.map((r) => r.id));
    }
  };

  return (
    <Modal
      title="Bulk Create Mirrors"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={isLoading}
      okText={`Create ${selectedRepoIds.length} Mirror(s)`}
      cancelText="Cancel"
      width={640}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          name="default_target_namespace"
          label="Target Namespace"
          rules={[{ required: true, message: 'Target namespace is required' }]}
        >
          <Input placeholder="e.g. mirrored" />
        </Form.Item>

        <Form.Item
          name="sync_group_id"
          label="Sync Group"
          rules={[{ required: true, message: 'Please select a sync group' }]}
        >
          <Select
            placeholder="Select sync group"
            loading={sgLoading}
            options={syncGroups.map((sg) => ({
              label: sg.name + (sg.is_default ? ' (default)' : ''),
              value: sg.id,
            }))}
          />
        </Form.Item>

        <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
          Select Repositories ({selectedRepoIds.length} / {filteredRepos.length})
        </Typography.Text>

        <Input.Search
          placeholder="Filter repositories..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ marginBottom: 8 }}
          allowClear
        />

        {!reposLoading && filteredRepos.length > 0 && (
          <Checkbox
            checked={selectedRepoIds.length === filteredRepos.length && filteredRepos.length > 0}
            indeterminate={
              selectedRepoIds.length > 0 && selectedRepoIds.length < filteredRepos.length
            }
            onChange={toggleAll}
          >
            Select All
          </Checkbox>
        )}

        {reposLoading ? (
          <Spin style={{ display: 'block', margin: '20px auto' }} />
        ) : filteredRepos.length === 0 ? (
          <Empty description="No repositories found" />
        ) : (
          <List
            size="small"
            style={{ maxHeight: 300, overflow: 'auto' }}
            dataSource={filteredRepos as SourceRepository[]}
            renderItem={(repo: SourceRepository) => (
              <List.Item>
                <Checkbox
                  checked={selectedRepoIds.includes(repo.id)}
                  onChange={() => toggleRepo(repo.id)}
                >
                  {repo.full_name}
                </Checkbox>
              </List.Item>
            )}
          />
        )}

        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 12 }}>
          Target project names will be auto-generated from repository names.
          A mirror will be created for each selected repository.
        </Typography.Text>
      </Form>
    </Modal>
  );
}

export default BulkCreateMirrorsModal;
