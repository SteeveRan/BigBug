/**
 * @file Admin/SystemProviders/SystemProviderFormModal.tsx
 * @description Edit modal for a system provider. Subtype/domain/category are
 *              immutable and shown read-only; the remaining editable fields are
 *              rendered from the subtype registry. The edit form also runs
 *              POST /providers/{id}/test and reports the result via antd message.
 * @dependencies antd, @ant-design/icons, RTK Query, ../../../types
 * @relatedFiles ./index.tsx
 */

import { useEffect, useMemo } from 'react';
import {
  App,
  Button,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import {
  useUpdateProviderMutation,
  useTestProviderMutation,
  useGetProviderTypesQuery,
  useGetCredentialsQuery,
} from '../../../store/api';
import type {
  ProviderCategory,
  ProviderDirection,
  ProviderDomain,
  ProviderTypeSpec,
  ResourceProvider,
  CredentialDetail,
} from '../../../types';

interface SystemProviderFormModalProps {
  open: boolean;
  provider?: ResourceProvider;
  onClose: () => void;
}

interface FormValues {
  label: string;
  description?: string;
  base_url?: string;
  direction: ProviderDirection;
  credential_id?: number;
  verify_ssl: boolean;
  priority: number;
  is_active: boolean;
  is_default: boolean;
  config: Record<string, unknown>;
}

// Deny-list of secret-like config keys rejected client-side (mirrors backend rule 11.1.2).
const SECRET_KEY_PATTERN =
  /(token|password|secret|passwd|api_key|access_key|private_key|credential)/i;

const DOMAIN_LABELS: Record<ProviderDomain, string> = {
  git: 'Git',
  docker: 'Docker',
  helm: 'Helm',
};

const CATEGORY_LABELS: Record<ProviderCategory, string> = {
  system: 'System',
  public: 'Public',
  private: 'Private',
};

const humanizeKey = (key: string): string =>
  key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

export function SystemProviderFormModal({ open, provider, onClose }: SystemProviderFormModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();

  const { data: types = [] } = useGetProviderTypesQuery();
  const { data: credentials = [] } = useGetCredentialsQuery();

  const [updateProvider, { isLoading: isUpdating }] = useUpdateProviderMutation();
  const [testConnection, { isLoading: isTesting }] = useTestProviderMutation();

  const spec = useMemo<ProviderTypeSpec | undefined>(
    () => types.find((t: ProviderTypeSpec) => t.subtype === provider?.subtype),
    [types, provider?.subtype]
  );

  useEffect(() => {
    if (!open || !provider) return;
    form.setFieldsValue({
      label: provider.label,
      description: provider.description ?? undefined,
      base_url: provider.base_url ?? undefined,
      direction: provider.direction,
      credential_id: provider.credential_id ?? undefined,
      verify_ssl: provider.verify_ssl,
      priority: provider.priority,
      is_active: provider.is_active,
      is_default: provider.is_default,
      config: provider.config ?? {},
    });
  }, [open, provider, form]);

  const allowedCredentialTypes = useMemo(() => spec?.allowed_credential_types ?? [], [spec]);
  const credentialOptions = useMemo(
    () =>
      (credentials as CredentialDetail[])
        .filter((c) => allowedCredentialTypes.includes(c.credential_type))
        .map((c) => ({ label: c.name, value: c.id })),
    [credentials, allowedCredentialTypes]
  );

  const validateConfig = (config: Record<string, unknown>): boolean => {
    for (const key of Object.keys(config)) {
      if (SECRET_KEY_PATTERN.test(key)) {
        message.error(`Секретные ключи (${key}) не допускаются в config — используйте credential`);
        return false;
      }
    }
    return true;
  };

  const handleTest = async () => {
    if (!provider) return;
    try {
      const result = await testConnection(provider.id).unwrap();
      if (result.ok || result.status_flag === 0) {
        message.success(result.status_text ?? 'Connection successful');
      } else {
        message.error(result.status_text ?? 'Connection test failed');
      }
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Connection test failed');
    }
  };

  const handleSubmit = async (values: FormValues) => {
    const config = values.config ?? {};
    if (!validateConfig(config)) return;
    if (!provider) return;

    try {
      await updateProvider({
        id: provider.id,
        data: {
          label: values.label,
          description: values.description,
          base_url: values.base_url,
          direction: values.direction,
          config,
          credential_id: values.credential_id,
          verify_ssl: values.verify_ssl,
          priority: values.priority,
          is_active: values.is_active,
          is_default: values.is_default,
        },
      }).unwrap();
      message.success('Изменения сохранены');
      onClose();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Не удалось сохранить провайдера');
    }
  };

  const renderConfigFields = () => {
    if (!spec) return null;
    const properties = spec.config_schema.properties ?? {};
    return Object.entries(properties).map(([key, field]) => {
      const name = ['config', key];
      const label = humanizeKey(key);
      if (field.type === 'integer') {
        return (
          <Form.Item key={key} name={name} label={label}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
        );
      }
      if (field.type === 'boolean') {
        return (
          <Form.Item key={key} name={name} label={label} valuePropName="checked">
            <Switch />
          </Form.Item>
        );
      }
      if (field.type === 'array') {
        return (
          <Form.Item key={key} name={name} label={label}>
            <Select mode="tags" style={{ width: '100%' }} />
          </Form.Item>
        );
      }
      if (field.enum) {
        return (
          <Form.Item key={key} name={name} label={label}>
            <Select options={field.enum.map((v) => ({ label: String(v), value: v as string }))} />
          </Form.Item>
        );
      }
      return (
        <Form.Item key={key} name={name} label={label}>
          <Input />
        </Form.Item>
      );
    });
  };

  return (
    <Modal
      title={`Edit provider: ${provider?.label ?? ''}`}
      open={open}
      onCancel={onClose}
      width={640}
      destroyOnHidden
      footer={[
        <Button
          key="test"
          icon={<PlayCircleOutlined />}
          loading={isTesting}
          disabled={isUpdating}
          onClick={handleTest}
        >
          Test connection
        </Button>,
        <Button key="cancel" onClick={onClose} disabled={isUpdating}>
          Cancel
        </Button>,
        <Button key="save" type="primary" loading={isUpdating} onClick={() => form.submit()}>
          Save
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item label="Provider type">
          <Flex gap={8} wrap>
            <Tag color="gold">{spec?.label ?? provider?.subtype}</Tag>
            <Tag color="blue">{DOMAIN_LABELS[spec?.domain ?? provider?.domain ?? 'git']}</Tag>
            <Tag>{CATEGORY_LABELS[provider?.category ?? 'system']}</Tag>
            <Typography.Text type="secondary">Read-only</Typography.Text>
          </Flex>
        </Form.Item>

        <Form.Item name="label" label="Label" rules={[{ required: true }]}>
          <Input placeholder="e.g. GitHub main" />
        </Form.Item>

        <Form.Item name="description" label="Description">
          <Input.TextArea rows={2} />
        </Form.Item>

        {spec?.requires_base_url && (
          <Form.Item name="base_url" label="Base URL" rules={[{ required: true }]}>
            <Input placeholder="https://" />
          </Form.Item>
        )}

        <Form.Item name="direction" label="Direction" rules={[{ required: true }]}>
          <Select
            style={{ width: 140 }}
            options={(spec?.allowed_directions ?? ['external', 'internal']).map((d) => ({
              label: d === 'external' ? 'External' : 'Internal',
              value: d,
            }))}
          />
        </Form.Item>

        {spec && renderConfigFields()}

        <Form.Item name="credential_id" label="Credential">
          <Select
            allowClear
            placeholder="Select credential"
            options={credentialOptions}
            notFoundContent="No compatible credentials"
          />
        </Form.Item>

        <Space size="large" wrap>
          <Form.Item name="verify_ssl" label="Verify SSL" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="priority" label="Priority">
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="is_default" label="Default" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Space>
      </Form>
    </Modal>
  );
}

export default SystemProviderFormModal;
