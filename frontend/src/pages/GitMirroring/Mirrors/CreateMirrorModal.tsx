/**
 * @file CreateMirrorModal.tsx
 * @description Модалка создания/редактирования зеркала (Group F)
 * @dependencies antd, @ant-design/icons, RTK Query
 */

import { useEffect } from 'react';
import { Modal, Form, Select, Input, App, Typography } from 'antd';
import {
  useCreateMirrorV2Mutation,
  useUpdateMirrorV2Mutation,
  useGetSourceRepositoriesQuery,
  useGetSyncGroupsQuery,
} from '../../../store/api';
import type { Mirror, MirrorCreate, MirrorUpdate } from '../../../types';

interface CreateMirrorModalProps {
  open: boolean;
  onClose: () => void;
  mirror?: Mirror;
  /** ID группы, из которой выбираем source repositories (опционально) */
  groupId?: number;
}

interface FormValues {
  source_repository_id: number;
  target_namespace: string;
  target_project_name: string;
  sync_group_id: number;
}

export function CreateMirrorModal({ open, onClose, mirror, groupId }: CreateMirrorModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const isEdit = !!mirror;

  const [createMirror, { isLoading: isCreating }] = useCreateMirrorV2Mutation();
  const [updateMirror, { isLoading: isUpdating }] = useUpdateMirrorV2Mutation();
  const isLoading = isCreating || isUpdating;

  // Fetch source repositories — pass group_id if available, else pass 0 (all)
  const { data: repositories = [], isLoading: reposLoading } = useGetSourceRepositoriesQuery(
    { group_id: groupId ?? 0 },
    { skip: !open }
  );

  // Fetch sync groups
  const { data: syncGroups = [], isLoading: syncGroupsLoading } = useGetSyncGroupsQuery(undefined, {
    skip: !open,
  });

  // Reset form on open
  useEffect(() => {
    if (open) {
      if (mirror) {
        form.setFieldsValue({
          source_repository_id: mirror.source_repository_id,
          target_namespace: mirror.target_namespace,
          target_project_name: mirror.target_project_name,
          sync_group_id: mirror.sync_group_id,
        });
      } else {
        form.resetFields();
      }
    }
  }, [open, mirror, form]);

  const handleSubmit = async (values: FormValues) => {
    try {
      if (isEdit && mirror) {
        const data: MirrorUpdate = {
          target_namespace: values.target_namespace,
          target_project_name: values.target_project_name,
          sync_group_id: values.sync_group_id,
        };
        await updateMirror({ id: mirror.id, data }).unwrap();
        message.success('Mirror updated successfully');
      } else {
        const data: MirrorCreate = {
          source_repository_id: values.source_repository_id,
          target_namespace: values.target_namespace,
          target_project_name: values.target_project_name,
          sync_group_id: values.sync_group_id,
        };
        await createMirror(data).unwrap();
        message.success('Mirror created successfully');
      }
      onClose();
    } catch {
      // error handled by RTK Query
    }
  };

  return (
    <Modal
      title={isEdit ? 'Edit Mirror' : 'Create Mirror'}
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={isLoading}
      okText={isEdit ? 'Update' : 'Create'}
      cancelText="Cancel"
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={
          mirror
            ? {
                source_repository_id: mirror.source_repository_id,
                target_namespace: mirror.target_namespace,
                target_project_name: mirror.target_project_name,
                sync_group_id: mirror.sync_group_id,
              }
            : undefined
        }
      >
        <Form.Item
          name="source_repository_id"
          label="Source Repository"
          rules={[{ required: true, message: 'Please select a source repository' }]}
        >
          <Select
            showSearch
            placeholder="Select source repository"
            loading={reposLoading}
            disabled={isEdit}
            optionFilterProp="label"
            options={(repositories ?? []).map((repo) => ({
              label: repo.full_name,
              value: repo.id,
            }))}
          />
        </Form.Item>

        <Form.Item
          name="target_namespace"
          label="Target Namespace"
          rules={[{ required: true, message: 'Target namespace is required' }]}
        >
          <Input placeholder="e.g. my-group" />
        </Form.Item>

        <Form.Item
          name="target_project_name"
          label="Target Project Name"
          rules={[{ required: true, message: 'Target project name is required' }]}
        >
          <Input
            placeholder="e.g. my-project"
            onChange={(e) => {
              // Auto-fill from source repository if creating
              if (!isEdit && e.target.value === '') {
                const selectedRepo = repositories?.find(
                  (r) => r.id === form.getFieldValue('source_repository_id')
                );
                if (selectedRepo) {
                  // Only auto-fill once if user hasn't typed
                }
              }
            }}
          />
        </Form.Item>

        <Form.Item
          name="sync_group_id"
          label="Sync Group"
          rules={[{ required: true, message: 'Please select a sync group' }]}
        >
          <Select
            placeholder="Select sync group"
            loading={syncGroupsLoading}
            options={syncGroups.map((sg) => ({
              label: sg.name + (sg.is_default ? ' (default)' : ''),
              value: sg.id,
            }))}
          />
        </Form.Item>

        <Typography.Text type="secondary">
          {isEdit
            ? 'Update mirror target or sync group assignment.'
            : 'Create a new mirror from the selected source repository to GitLab. Supports GitHub, GitLab, Bitbucket, and Generic Git.'}
        </Typography.Text>
      </Form>
    </Modal>
  );
}

export default CreateMirrorModal;
