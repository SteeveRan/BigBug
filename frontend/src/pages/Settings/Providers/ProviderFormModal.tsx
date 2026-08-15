/**
 * @file Settings/Providers/ProviderFormModal.tsx
 * @description Create/edit modal for a unified provider. Dynamically renders config
 *              fields from `/api/providers/types`, filters credentials by allowed
 *              types, and offers visibility (owner/team/public) when permitted.
 * @dependencies antd, RTK Query, ../../../types
 * @relatedFiles ./index.tsx, ./CredentialAssignModal.tsx
 */

import { useEffect, useMemo, useState } from 'react';
import { App, Button, Form, Input, InputNumber, Modal, Radio, Select, Space, Switch } from 'antd';
import {
  useCreateProviderMutation,
  useUpdateProviderMutation,
  useGetProviderTypesQuery,
  useGetCredentialsQuery,
  useGetTeamsQuery,
} from '../../../store/api';
import type {
  ProviderCategory,
  ProviderDirection,
  ProviderSubtype,
  ProviderTypeSpec,
  ProviderVisibility,
  ResourceProvider,
  CredentialDetail,
  Team,
} from '../../../types';
import { usePermissions } from '../../../hooks/usePermissions';

interface ProviderFormModalProps {
  open: boolean;
  provider?: ResourceProvider;
  onClose: () => void;
}

interface FormValues {
  subtype: ProviderSubtype;
  category: ProviderCategory;
  direction: ProviderDirection;
  label: string;
  description?: string;
  base_url?: string;
  credential_id?: number;
  visibility: ProviderVisibility;
  team_id?: number;
  verify_ssl: boolean;
  priority: number;
  config: Record<string, unknown>;
}

// Deny-list of secret-like config keys rejected client-side (mirrors backend rule 11.1.2).
const SECRET_KEY_PATTERN =
  /(token|password|secret|passwd|api_key|access_key|private_key|credential)/i;

export function ProviderFormModal({ open, provider, onClose }: ProviderFormModalProps) {
  const { message } = App.useApp();
  const { hasPermission } = usePermissions();
  const [form] = Form.useForm<FormValues>();
  const isEdit = !!provider;

  const { data: types = [] } = useGetProviderTypesQuery();
  const { data: credentials = [] } = useGetCredentialsQuery();
  const { data: teams = [] } = useGetTeamsQuery();

  const [createProvider, { isLoading: isCreating }] = useCreateProviderMutation();
  const [updateProvider, { isLoading: isUpdating }] = useUpdateProviderMutation();
  const isLoading = isCreating || isUpdating;

  const [selectedSubtype, setSelectedSubtype] = useState<ProviderSubtype | undefined>();
  const [selectedCategory, setSelectedCategory] = useState<ProviderCategory>('private');

  const spec = useMemo<ProviderTypeSpec | undefined>(
    () => types.find((t: ProviderTypeSpec) => t.subtype === selectedSubtype),
    [types, selectedSubtype]
  );

  const canChooseSystem = hasPermission('providers_system:write');
  const canChoosePublic = hasPermission('providers:share');

  useEffect(() => {
    if (!open) return;
    if (provider) {
      form.setFieldsValue({
        subtype: provider.subtype,
        category: provider.category,
        direction: provider.direction,
        label: provider.label,
        description: provider.description ?? undefined,
        base_url: provider.base_url ?? undefined,
        credential_id: provider.credential_id ?? undefined,
        visibility: provider.visibility,
        team_id: provider.team_id ?? undefined,
        verify_ssl: provider.verify_ssl,
        priority: provider.priority,
        config: provider.config ?? {},
      });
      setSelectedSubtype(provider.subtype);
      setSelectedCategory(provider.category);
    } else {
      form.resetFields();
      form.setFieldsValue({
        category: 'private',
        visibility: 'owner',
        verify_ssl: true,
        priority: 0,
        config: {},
      });
      setSelectedSubtype(undefined);
      setSelectedCategory('private');
    }
  }, [open, provider, form]);

  const allowedCredentialTypes = useMemo(() => spec?.allowed_credential_types ?? [], [spec]);
  const credentialOptions = useMemo(
    () =>
      (credentials as CredentialDetail[])
        .filter((c) => allowedCredentialTypes.includes(c.credential_type))
        .map((c) => ({ label: c.name, value: c.id })),
    [credentials, allowedCredentialTypes]
  );

  const teamOptions = useMemo(
    () => (teams as Team[]).map((t) => ({ label: t.name, value: t.id })),
    [teams]
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

  const handleSubmit = async (values: FormValues) => {
    const config = values.config ?? {};
    if (!validateConfig(config)) return;

    const name = values.label
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    const domain = spec?.domain ?? 'git';

    try {
      if (isEdit && provider) {
        await updateProvider({
          id: provider.id,
          data: {
            category: values.category,
            direction: values.direction,
            label: values.label,
            description: values.description,
            base_url: values.base_url,
            config,
            credential_id: values.credential_id,
            visibility: values.visibility,
            team_id: values.visibility === 'team' ? values.team_id : undefined,
            verify_ssl: values.verify_ssl,
            priority: values.priority,
          },
        }).unwrap();
        message.success('Изменения сохранены');
      } else {
        await createProvider({
          domain,
          name,
          subtype: values.subtype,
          category: values.category,
          direction: values.direction,
          label: values.label,
          description: values.description,
          base_url: values.base_url,
          config,
          credential_id: values.credential_id,
          visibility: values.visibility,
          team_id: values.visibility === 'team' ? values.team_id : undefined,
        }).unwrap();
        message.success('Провайдер создан');
      }
      onClose();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Не удалось сохранить провайдера');
    }
  };

  const categoryOptions = [
    { label: 'Private', value: 'private' },
    ...(canChoosePublic ? [{ label: 'Public', value: 'public' }] : []),
    ...(canChooseSystem ? [{ label: 'System', value: 'system' }] : []),
  ];

  const renderConfigFields = () => {
    if (!spec) return null;
    const properties = spec.config_schema.properties ?? {};
    return Object.entries(properties).map(([key, field]) => {
      const name = ['config', key];
      if (field.type === 'integer') {
        return (
          <Form.Item key={key} name={name} label={key}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
        );
      }
      if (field.type === 'boolean') {
        return (
          <Form.Item key={key} name={name} label={key} valuePropName="checked">
            <Switch />
          </Form.Item>
        );
      }
      if (field.type === 'array') {
        return (
          <Form.Item key={key} name={name} label={key}>
            <Select mode="tags" style={{ width: '100%' }} />
          </Form.Item>
        );
      }
      if (field.enum) {
        return (
          <Form.Item key={key} name={name} label={key}>
            <Select options={field.enum.map((v) => ({ label: String(v), value: v as string }))} />
          </Form.Item>
        );
      }
      return (
        <Form.Item key={key} name={name} label={key}>
          <Input />
        </Form.Item>
      );
    });
  };

  return (
    <Modal
      title={isEdit ? `Edit provider: ${provider?.label}` : 'Create provider'}
      open={open}
      onCancel={onClose}
      width={640}
      destroyOnHidden
      footer={[
        <Button key="cancel" onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>,
        <Button key="save" type="primary" loading={isLoading} onClick={() => form.submit()}>
          {isEdit ? 'Save' : 'Create'}
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item name="subtype" label="Subtype" rules={[{ required: true }]}>
          <Select
            placeholder="Select subtype"
            options={types.map((t: ProviderTypeSpec) => ({
              label: `${t.label} (${t.domain})`,
              value: t.subtype,
            }))}
            onChange={(v) => setSelectedSubtype(v)}
          />
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

        <Space size="large" wrap>
          <Form.Item name="category" label="Category" rules={[{ required: true }]}>
            <Radio.Group
              options={categoryOptions}
              onChange={(e) => setSelectedCategory(e.target.value)}
            />
          </Form.Item>
          <Form.Item name="direction" label="Direction" rules={[{ required: true }]}>
            <Select
              style={{ width: 140 }}
              options={(spec?.allowed_directions ?? ['external', 'internal']).map((d) => ({
                label: d === 'external' ? 'External' : 'Internal',
                value: d,
              }))}
            />
          </Form.Item>
        </Space>

        <Form.Item
          name="visibility"
          label="Visibility"
          rules={[{ required: true }]}
          tooltip="Public is only available for private providers with providers:share"
        >
          <Radio.Group
            options={[
              { label: 'Only me', value: 'owner' },
              { label: 'Team', value: 'team' },
              ...(canChoosePublic && selectedCategory === 'private'
                ? [{ label: 'All users', value: 'public' }]
                : []),
            ]}
          />
        </Form.Item>

        <Form.Item noStyle shouldUpdate>
          {() =>
            form.getFieldValue('visibility') === 'team' ? (
              <Form.Item name="team_id" label="Team" rules={[{ required: true }]}>
                <Select options={teamOptions} placeholder="Select team" />
              </Form.Item>
            ) : null
          }
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
        </Space>
      </Form>
    </Modal>
  );
}

export default ProviderFormModal;
