/**
 * @file PipelineModal.tsx
 * @description Модалка создания/редактирования Pipeline Configuration
 * @dependencies antd, RTK Query, types
 */

import { useState, useEffect } from 'react';
import { Modal, Form, Input, Select, Switch, Typography, App } from 'antd';
import {
  useCreatePipelineConfigMutation,
  useUpdatePipelineConfigMutation,
  useGetProvidersQuery,
  useGetComponentsQuery,
} from '../../../store/api';
import type { PipelineConfig, PipelineConfigCreate, PipelineConfigUpdate } from '../../../types';

interface PipelineModalProps {
  open: boolean;
  onClose: () => void;
  pipeline?: PipelineConfig | null;
}

interface FormValues {
  name: string;
  description?: string;
  provider_id?: number | null;
  ref?: string;
  is_default: boolean;
  is_enabled: boolean;
  default_variables_json?: string;
  component_ids?: number[];
}

export function PipelineModal({ open, onClose, pipeline }: PipelineModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const isEdit = !!pipeline;

  const [createConfig, { isLoading: isCreating }] = useCreatePipelineConfigMutation();
  const [updateConfig, { isLoading: isUpdating }] = useUpdatePipelineConfigMutation();
  const { data: providers = [] } = useGetProvidersQuery({
    subtype: 'gitlab',
    category: 'system',
    direction: 'internal',
  });
  const { data: components = [] } = useGetComponentsQuery();
  const isLoading = isCreating || isUpdating;

  const [jsonError, setJsonError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      if (pipeline) {
        form.setFieldsValue({
          name: pipeline.name,
          description: pipeline.description ?? undefined,
          provider_id: pipeline.provider_id ?? undefined,
          ref: pipeline.ref ?? 'main',
          is_default: pipeline.is_default,
          is_enabled: pipeline.is_enabled,
          default_variables_json: pipeline.default_variables
            ? JSON.stringify(pipeline.default_variables, null, 2)
            : undefined,
          component_ids: pipeline.components?.map((c) => c.component_id) ?? [],
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          ref: 'main',
          is_default: false,
          is_enabled: true,
        });
      }
      setJsonError(null);
    }
  }, [open, pipeline, form]);

  const validateJson = (_: unknown, value?: string) => {
    if (!value || value.trim() === '') {
      setJsonError(null);
      return Promise.resolve();
    }
    try {
      JSON.parse(value);
      setJsonError(null);
      return Promise.resolve();
    } catch {
      setJsonError('Invalid JSON format');
      return Promise.reject(new Error('Invalid JSON format'));
    }
  };

  const handleSubmit = async (values: FormValues) => {
    let defaultVariables: Record<string, unknown> | undefined;
    if (values.default_variables_json?.trim()) {
      try {
        defaultVariables = JSON.parse(values.default_variables_json);
      } catch {
        message.error('Invalid JSON in default variables');
        return;
      }
    }

    try {
      if (isEdit && pipeline) {
        const data: PipelineConfigUpdate = {
          description: values.description ?? null,
          provider_id: values.provider_id ?? null,
          ref: values.ref ?? null,
          default_variables: defaultVariables ?? null,
          is_default: values.is_default ?? null,
          is_enabled: values.is_enabled ?? null,
          components:
            values.component_ids?.map((cid) => ({
              component_id: cid,
              order: 0,
            })) ?? null,
        };
        await updateConfig({ id: pipeline.id, data }).unwrap();
        message.success('Pipeline configuration updated successfully');
      } else {
        const data: PipelineConfigCreate = {
          name: values.name,
          description: values.description ?? null,
          provider_id: values.provider_id ?? null,
          ref: values.ref ?? 'main',
          default_variables: defaultVariables ?? null,
          is_default: values.is_default ?? null,
          is_enabled: values.is_enabled,
          components:
            values.component_ids?.map((cid) => ({
              component_id: cid,
              order: 0,
            })) ?? null,
        };
        await createConfig(data).unwrap();
        message.success('Pipeline configuration created successfully');
      }
      onClose();
    } catch {
      // error handled by RTK Query
    }
  };

  const providerOptions = providers.map((p) => ({
    label: p.label,
    value: p.id,
  }));

  const componentOptions = components.map((comp) => ({
    label: comp.name,
    value: comp.id,
  }));

  return (
    <Modal
      title={isEdit ? 'Edit Pipeline Configuration' : 'Create Pipeline Configuration'}
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={isLoading}
      okText={isEdit ? 'Update' : 'Create'}
      cancelText="Cancel"
      destroyOnHidden
      width={640}
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: 'Pipeline name is required' }]}
        >
          <Input placeholder="e.g. Default Mirror Pipeline" disabled={isEdit} />
        </Form.Item>

        <Form.Item name="description" label="Description">
          <Input.TextArea
            placeholder="Optional description of this pipeline configuration"
            rows={2}
          />
        </Form.Item>

        <Form.Item name="provider_id" label="GitLab Provider">
          <Select
            placeholder="Select GitLab provider (optional)"
            allowClear
            options={providerOptions}
          />
        </Form.Item>

        <Form.Item name="ref" label="Default Ref">
          <Input placeholder="main" />
        </Form.Item>

        <Form.Item name="is_default" label="Default" valuePropName="checked">
          <Switch />
        </Form.Item>

        <Form.Item name="is_enabled" label="Enabled" valuePropName="checked">
          <Switch />
        </Form.Item>

        <Form.Item
          name="default_variables_json"
          label="Default Variables (JSON)"
          validateTrigger={['onChange', 'onBlur']}
          rules={[{ validator: validateJson }]}
          help={jsonError ?? 'Enter a valid JSON object, e.g. {"KEY": "value"}'}
          validateStatus={jsonError ? 'error' : undefined}
        >
          <Input.TextArea placeholder='{"VAR_NAME": "default_value"}' rows={4} />
        </Form.Item>

        <Form.Item name="component_ids" label="Components">
          <Select
            mode="multiple"
            placeholder="Select GitLab components"
            options={componentOptions}
            allowClear
          />
        </Form.Item>

        <Typography.Text type="secondary">
          {isEdit
            ? 'Update the pipeline configuration. Name cannot be changed.'
            : 'Create a new pipeline configuration with optional components and default variables.'}
        </Typography.Text>
      </Form>
    </Modal>
  );
}

export default PipelineModal;
