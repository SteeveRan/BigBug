/**
 * @file ProviderModal.tsx
 * @description Модалка создания/редактирования Source Provider (Group F)
 * @dependencies antd, RTK Query
 */

import { useEffect } from 'react';
import { Modal, Form, Select, Input, App, Typography } from 'antd';
import {
  useCreateSourceProviderMutation,
  useUpdateSourceProviderMutation,
} from '../../../store/api';
import type {
  SourceProvider,
  SourceProviderCreate,
  SourceProviderUpdate,
  ProviderType,
} from '../../../types';

interface ProviderModalProps {
  open: boolean;
  onClose: () => void;
  provider?: SourceProvider;
}

interface FormValues {
  name: string;
  provider_type: ProviderType;
  credential_id: number;
}

const PROVIDER_TYPES = [
  { label: 'GitHub', value: 'github' },
  { label: 'GitLab', value: 'gitlab' },
  { label: 'Bitbucket', value: 'bitbucket' },
  { label: 'Generic Git', value: 'generic' },
];

export function ProviderModal({ open, onClose, provider }: ProviderModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const isEdit = !!provider;

  const [createProvider, { isLoading: isCreating }] = useCreateSourceProviderMutation();
  const [updateProvider, { isLoading: isUpdating }] = useUpdateSourceProviderMutation();
  const isLoading = isCreating || isUpdating;

  useEffect(() => {
    if (open) {
      if (provider) {
        form.setFieldsValue({
          name: provider.name,
          provider_type: provider.provider_type,
          credential_id: provider.credential_id,
        });
      } else {
        form.resetFields();
      }
    }
  }, [open, provider, form]);

  const handleSubmit = async (values: FormValues) => {
    try {
      if (isEdit && provider) {
        const data: SourceProviderUpdate = {
          name: values.name,
          credential_id: values.credential_id,
        };
        await updateProvider({ id: provider.id, data }).unwrap();
        message.success('Provider updated successfully');
      } else {
        const data: SourceProviderCreate = {
          name: values.name,
          provider_type: values.provider_type,
          credential_id: values.credential_id,
        };
        await createProvider(data).unwrap();
        message.success('Provider created successfully');
      }
      onClose();
    } catch {
      // error handled by RTK Query
    }
  };

  return (
    <Modal
      title={isEdit ? 'Edit Provider' : 'Add Provider'}
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={isLoading}
      okText={isEdit ? 'Update' : 'Create'}
      cancelText="Cancel"
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          name="name"
          label="Label"
          rules={[{ required: true, message: 'Provider label is required' }]}
        >
          <Input placeholder="e.g. My GitHub Org" />
        </Form.Item>

        <Form.Item
          name="provider_type"
          label="Provider Type"
          rules={[{ required: true, message: 'Provider type is required' }]}
        >
          <Select placeholder="Select provider type" disabled={isEdit} options={PROVIDER_TYPES} />
        </Form.Item>

        <Form.Item
          name="credential_id"
          label="Credential"
          rules={[{ required: true, message: 'Credential is required' }]}
        >
          <Select
            placeholder="Select credential"
            options={[
              { label: 'Default GitHub Token', value: 1 },
              { label: 'Default GitLab Token', value: 2 },
            ]}
          />
        </Form.Item>

        <Typography.Text type="secondary">
          {isEdit
            ? 'Update provider label or credential.'
            : 'Create a new source provider to connect to GitHub, GitLab, Bitbucket, or any Git server via Generic Git.'}
        </Typography.Text>
      </Form>
    </Modal>
  );
}

export default ProviderModal;
