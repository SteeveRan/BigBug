/**
 * @file AddRepositoryModal.tsx
 * @description Модалка ручного добавления Source Repository (для Generic Git провайдеров)
 * @dependencies antd, RTK Query
 */

import { useEffect, useMemo } from 'react';
import { Modal, Form, Select, Input, App, Typography } from 'antd';
import {
  useCreateSourceRepositoryMutation,
  useGetSourceGroupsQuery,
  useGetSourceProvidersQuery,
} from '../../../store/api';
import type { ProviderType, SourceProvider, SourceRepositoryCreate } from '../../../types';

interface AddRepositoryModalProps {
  open: boolean;
  onClose: () => void;
  /** Preselected source group id (optional) */
  preselectedGroupId?: number;
  /** Preselected provider id (optional) */
  preselectedProviderId?: number;
}

interface FormValues {
  provider_type: ProviderType;
  clone_url: string;
  source_group_id?: number;
  description?: string;
}

export function AddRepositoryModal({ open, onClose, preselectedGroupId, preselectedProviderId }: AddRepositoryModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();

  const [createRepo, { isLoading }] = useCreateSourceRepositoryMutation();

  const { data: providers = [] } = useGetSourceProvidersQuery(undefined, { skip: !open });

  // Resolve the selected provider to auto-fill provider_type
  const preselectedProvider = useMemo<SourceProvider | undefined>(() => {
    if (preselectedProviderId != null) {
      return providers.find((p) => p.id === preselectedProviderId);
    }
    return undefined;
  }, [preselectedProviderId, providers]);

  const providerId = preselectedProviderId ?? providers[0]?.id ?? 0;
  const { data: groups = [], isLoading: groupsLoading } = useGetSourceGroupsQuery(providerId, {
    skip: !open || providerId === 0,
  });

  // Reset on open
  useEffect(() => {
    if (open) {
      form.resetFields();
      if (preselectedGroupId) {
        form.setFieldValue('source_group_id', preselectedGroupId);
      }
      if (preselectedProvider) {
        form.setFieldValue('provider_type', preselectedProvider.provider_type);
      }
    }
  }, [open, form, preselectedGroupId, preselectedProvider]);

  const handleSubmit = async (values: FormValues) => {
    try {
      const data: SourceRepositoryCreate = {
        provider_type: values.provider_type,
        clone_url: values.clone_url.trim(),
        source_group_id: values.source_group_id || undefined,
        description: values.description || undefined,
      };
      await createRepo(data).unwrap();
      message.success(`Repository added successfully`);
      onClose();
    } catch {
      // error handled by RTK Query
    }
  };

  return (
    <Modal
      title="Add Repository"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={isLoading}
      okText="Add"
      cancelText="Cancel"
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          name="provider_type"
          label="Provider Type"
          rules={[{ required: true, message: 'Please select a provider type' }]}
        >
          <Select
            placeholder="Select provider type"
            options={[
              { label: 'GitHub', value: 'github' },
              { label: 'GitLab', value: 'gitlab' },
              { label: 'Generic Git', value: 'generic' },
            ]}
          />
        </Form.Item>

        <Form.Item
          name="clone_url"
          label="Clone URL"
          rules={[{ required: true, message: 'Clone URL is required' }]}
        >
          <Input placeholder="https://git.example.com/owner/my-repo.git or git@..." />
        </Form.Item>

        <Form.Item
          name="source_group_id"
          label="Source Group (optional)"
        >
          <Select
            showSearch
            allowClear
            placeholder="Select source group (optional)"
            loading={groupsLoading}
            optionFilterProp="label"
            options={groups.map((g) => ({
              label: g.full_name || g.name,
              value: g.id,
            }))}
          />
        </Form.Item>

        <Form.Item name="description" label="Description">
          <Input.TextArea rows={3} placeholder="Repository description..." />
        </Form.Item>

        <Typography.Text type="secondary">
          Manually add a repository from any Git provider. The clone URL is parsed
          automatically to derive name and full name.
          For GitHub/GitLab, use the Import Group flow instead — it auto-discovers
          all repositories.
        </Typography.Text>
      </Form>
    </Modal>
  );
}

export default AddRepositoryModal;
