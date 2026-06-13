/**
 * @file ImportGroupModal.tsx
 * @description Модалка импорта Source Group (Group F)
 * @dependencies antd, RTK Query
 */

import { Modal, Form, Select, Input, App } from 'antd';
import { useImportSourceGroupMutation, useGetSourceProvidersQuery } from '../../../store/api';

interface ImportGroupModalProps {
  open: boolean;
  onClose: () => void;
}

interface FormValues {
  provider_id: number;
  group_name: string;
}

export function ImportGroupModal({ open, onClose }: ImportGroupModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();

  const [importGroup, { isLoading }] = useImportSourceGroupMutation();
  const { data: providers = [], isLoading: providersLoading } = useGetSourceProvidersQuery(
    undefined,
    { skip: !open }
  );

  const handleSubmit = async (values: FormValues) => {
    try {
      await importGroup({
        provider_id: values.provider_id,
        group_name: values.group_name,
      }).unwrap();
      message.success('Group imported successfully');
      form.resetFields();
      onClose();
    } catch {
      // error handled by RTK Query
    }
  };

  return (
    <Modal
      title="Import Group"
      open={open}
      onCancel={() => {
        form.resetFields();
        onClose();
      }}
      onOk={() => form.submit()}
      confirmLoading={isLoading}
      okText="Import"
      cancelText="Cancel"
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          name="provider_id"
          label="Provider"
          rules={[{ required: true, message: 'Please select a provider' }]}
        >
          <Select
            placeholder="Select provider"
            loading={providersLoading}
            options={providers.map((p) => ({
              label: `${p.name} (${p.provider_type})`,
              value: p.id,
            }))}
          />
        </Form.Item>

        <Form.Item
          name="group_name"
          label="Group Name"
          rules={[{ required: true, message: 'Group name is required' }]}
        >
          <Input placeholder="e.g. my-organization" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default ImportGroupModal;
