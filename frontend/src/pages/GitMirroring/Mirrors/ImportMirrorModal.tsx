/**
 * @file ImportMirrorModal.tsx
 * @description Модалка импорта существующего зеркала (Group F)
 * @dependencies antd, RTK Query
 */

import { Modal, Form, Select, Input, App, Alert } from 'antd';
import { useImportExistingMirrorMutation, useGetSourceRepositoriesQuery } from '../../../store/api';
import type { ImportMirrorRequest } from '../../../types';

interface ImportMirrorModalProps {
  open: boolean;
  onClose: () => void;
  groupId?: number;
}

interface FormValues {
  source_repository_id: number;
  target_namespace: string;
  target_project_name: string;
}

export function ImportMirrorModal({ open, onClose, groupId }: ImportMirrorModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();

  const [importMirror, { isLoading }] = useImportExistingMirrorMutation();

  const { data: repositories = [], isLoading: reposLoading } = useGetSourceRepositoriesQuery(
    { group_id: groupId ?? 0 },
    { skip: !open }
  );

  const handleSubmit = async (values: FormValues) => {
    try {
      const data: ImportMirrorRequest = {
        source_repository_id: values.source_repository_id,
        target_namespace: values.target_namespace,
        target_project_name: values.target_project_name,
      };
      await importMirror(data).unwrap();
      message.success('Mirror imported successfully');
      form.resetFields();
      onClose();
    } catch {
      // error handled by RTK Query
    }
  };

  return (
    <Modal
      title="Import Existing Mirror"
      open={open}
      onCancel={() => {
        form.resetFields();
        onClose();
      }}
      onOk={() => form.submit()}
      confirmLoading={isLoading}
      okText="Import"
      cancelText="Cancel"
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Alert
          title="Система проверит связь через сравнение commit history. Поддерживаются GitHub, GitLab и Generic Git репозитории."
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Form.Item
          name="source_repository_id"
          label="Source Repository"
          rules={[{ required: true, message: 'Please select a source repository' }]}
        >
          <Select
            showSearch
            placeholder="Select source repository"
            loading={reposLoading}
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
          <Input placeholder="e.g. my-project" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default ImportMirrorModal;
