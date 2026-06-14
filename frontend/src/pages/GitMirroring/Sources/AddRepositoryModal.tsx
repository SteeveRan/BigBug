/**
 * @file AddRepositoryModal.tsx
 * @description Модалка ручного добавления Source Repository
 * @dependencies antd, RTK Query
 */

import { useEffect, useMemo } from 'react';
import { Modal, Form, Select, Input, App, Typography } from 'antd';
import { useCreateSourceRepositoryMutation, useGetSourceProvidersQuery } from '../../../store/api';
import type { ProviderType, SourceProvider, SourceRepositoryCreate } from '../../../types';

interface AddRepositoryModalProps {
  open: boolean;
  onClose: () => void;
  /** Preselected provider id (optional) */
  preselectedProviderId?: number;
}

interface FormValues {
  provider_type: ProviderType;
  clone_url: string;
}

export function AddRepositoryModal({
  open,
  onClose,
  preselectedProviderId,
}: AddRepositoryModalProps) {
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

  // Reset on open
  useEffect(() => {
    if (open) {
      form.resetFields();
      if (preselectedProvider) {
        form.setFieldValue('provider_type', preselectedProvider.provider_type);
      }
    }
  }, [open, form, preselectedProvider]);

  const handleSubmit = async (values: FormValues) => {
    try {
      const data: SourceRepositoryCreate = {
        provider_type: values.provider_type,
        clone_url: values.clone_url.trim(),
      };
      await createRepo(data).unwrap();
      message.success(`Repository added successfully`);
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'data' in err
          ? (err as { data?: { detail?: string } }).data?.detail
          : undefined;
      message.error(detail || 'Failed to add repository');
    } finally {
      onClose();
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

        <Typography.Text type="secondary">
          Manually add a repository from any Git provider. The clone URL is parsed automatically to
          derive name, full name, and source group. For GitHub/GitLab, use the Import Group flow
          instead — it auto-discovers all repositories.
        </Typography.Text>
      </Form>
    </Modal>
  );
}

export default AddRepositoryModal;
