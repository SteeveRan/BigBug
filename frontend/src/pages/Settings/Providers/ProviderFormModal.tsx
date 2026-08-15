/**
 * @file Settings/Providers/ProviderFormModal.tsx
 * @description Create/edit modal for a unified provider. The provider "type" is the
 *              domain (git/docker/helm, chosen via Radio.Group); the "subtype" is a
 *              cascading Select fed by the selected domain. When a domain has exactly
 *              one subtype the Select is hidden and the subtype is set automatically.
 *              Credentials are entered inline (token / https-basic / ssh key) and an
 *              "Anonymous access" switch hides them and submits `credential_id: null`.
 *              System providers (category === 'system') are never offered here.
 * @dependencies antd, @ant-design/icons, RTK Query, ../../../types
 * @relatedFiles ./index.tsx, ./CredentialAssignModal.tsx
 */

import { useEffect, useMemo, useState } from 'react';
import {
  App,
  Button,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import {
  useCreateProviderMutation,
  useUpdateProviderMutation,
  useTestProviderMutation,
  useGetProviderTypesQuery,
  useGetCredentialsQuery,
  useGetTeamsQuery,
  useCreateCredentialMutation,
} from '../../../store/api';
import type {
  CredentialDetail,
  CredentialType,
  ProviderCategory,
  ProviderDirection,
  ProviderDomain,
  ProviderSubtype,
  ProviderTypeSpec,
  ProviderVisibility,
  ResourceProvider,
  Team,
} from '../../../types';
import { usePermissions } from '../../../hooks/usePermissions';

interface ProviderFormModalProps {
  open: boolean;
  provider?: ResourceProvider;
  onClose: () => void;
}

interface FormValues {
  subtype?: ProviderSubtype;
  category: ProviderCategory;
  direction: ProviderDirection;
  label: string;
  description?: string;
  base_url?: string;
  visibility: ProviderVisibility;
  team_id?: number;
  verify_ssl: boolean;
  priority: number;
  config: Record<string, unknown>;
  anonymous: boolean;
  credential_type?: CredentialType;
  credential_username?: string;
  credential_secret?: string;
  credential_ssh_public_key?: string;
}

// Deny-list of secret-like config keys rejected client-side (mirrors backend rule 11.1.2).
const SECRET_KEY_PATTERN =
  /(token|password|secret|passwd|api_key|access_key|private_key|credential)/i;

const DOMAIN_LABELS: Record<ProviderDomain, string> = {
  git: 'Git',
  docker: 'Docker',
  helm: 'Helm',
};

const DOMAIN_ORDER: ProviderDomain[] = ['git', 'docker', 'helm'];

const CREDENTIAL_TYPE_LABELS: Record<CredentialType, string> = {
  github_token: 'GitHub Token',
  gitlab_token: 'GitLab Token',
  https_basic: 'HTTPS Basic',
  ssh_key: 'SSH Key',
};

const secretLabel = (type: CredentialType): string => {
  if (type === 'ssh_key') return 'Private key';
  if (type === 'https_basic') return 'Password';
  return 'Token';
};

const humanizeKey = (key: string): string =>
  key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

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
  const [testConnection, { isLoading: isTesting }] = useTestProviderMutation();
  const [createCredential] = useCreateCredentialMutation();
  const isLoading = isCreating || isUpdating;

  const [selectedDomain, setSelectedDomain] = useState<ProviderDomain | undefined>();
  const [selectedSubtype, setSelectedSubtype] = useState<ProviderSubtype | undefined>();
  const [selectedCategory, setSelectedCategory] = useState<ProviderCategory>('private');

  // System providers cannot be created from this form: drop subtypes that only
  // support the `system` category so they never appear in the subtype Select.
  const availableTypes = useMemo<ProviderTypeSpec[]>(
    () =>
      (types as ProviderTypeSpec[]).filter((t) => t.allowed_categories.some((c) => c !== 'system')),
    [types]
  );

  const spec = useMemo<ProviderTypeSpec | undefined>(
    () => (types as ProviderTypeSpec[]).find((t) => t.subtype === selectedSubtype),
    [types, selectedSubtype]
  );

  const domainSubtypes = useMemo<ProviderTypeSpec[]>(
    () => (selectedDomain ? availableTypes.filter((t) => t.domain === selectedDomain) : []),
    [availableTypes, selectedDomain]
  );

  const canChoosePublic = hasPermission('providers:share');

  const allowedCredentialTypes = useMemo(
    () => (spec?.allowed_credential_types ?? []) as CredentialType[],
    [spec]
  );

  const teamOptions = useMemo(
    () => (teams as Team[]).map((t) => ({ label: t.name, value: t.id })),
    [teams]
  );

  // ── Initialise / reset on open ──────────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    if (provider) {
      setSelectedDomain(provider.domain);
      setSelectedSubtype(provider.subtype);
      setSelectedCategory(provider.category);
      form.setFieldsValue({
        subtype: provider.subtype,
        category: provider.category,
        direction: provider.direction,
        label: provider.label,
        description: provider.description ?? undefined,
        base_url: provider.base_url ?? undefined,
        visibility: provider.visibility,
        team_id: provider.team_id ?? undefined,
        verify_ssl: provider.verify_ssl,
        priority: provider.priority,
        config: provider.config ?? {},
        anonymous: !provider.has_credential,
      });
    } else {
      setSelectedDomain(undefined);
      setSelectedSubtype(undefined);
      setSelectedCategory('private');
      form.resetFields();
      form.setFieldsValue({
        category: 'private',
        visibility: 'owner',
        verify_ssl: true,
        priority: 0,
        config: {},
        anonymous: false,
      });
    }
  }, [open, provider, form]);

  // Auto-select the sole subtype for a domain (hide the Select).
  useEffect(() => {
    if (!open || isEdit) return;
    if (selectedDomain && domainSubtypes.length === 1) {
      setSelectedSubtype(domainSubtypes[0].subtype);
      form.setFieldValue('subtype', domainSubtypes[0].subtype);
    }
  }, [open, isEdit, selectedDomain, domainSubtypes, form]);

  // Dynamic fields (base_url / config) are only mounted once `spec` resolves, so
  // re-apply their values after the subtype is known — fixes empty fields on edit.
  useEffect(() => {
    if (!open || !provider || !spec) return;
    form.setFieldsValue({
      base_url: provider.base_url ?? undefined,
      config: provider.config ?? {},
    });
  }, [open, provider, spec, form]);

  // Prefill credential type/username from the already-assigned credential.
  useEffect(() => {
    if (!open || !provider?.credential_id) return;
    const credential = (credentials as CredentialDetail[]).find(
      (c) => c.id === provider.credential_id
    );
    if (credential) {
      form.setFieldsValue({
        credential_type: credential.credential_type,
        credential_username: credential.username ?? undefined,
      });
    }
  }, [open, provider, credentials, form]);

  const validateConfig = (config: Record<string, unknown>): boolean => {
    for (const key of Object.keys(config)) {
      if (SECRET_KEY_PATTERN.test(key)) {
        message.error(`Секретные ключи (${key}) не допускаются в config — используйте credential`);
        return false;
      }
    }
    return true;
  };

  const handleDomainChange = (domain: ProviderDomain) => {
    setSelectedDomain(domain);
    setSelectedSubtype(undefined);
    form.setFieldValue('subtype', undefined);
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

    const label = values.label;
    const name = label
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    const domain = spec?.domain ?? provider?.domain ?? 'git';
    const subtype = isEdit ? provider?.subtype : selectedSubtype;
    if (!subtype) return;

    try {
      // Credentials: anonymous → null; a typed secret → create a credential and
      // link its id; edit without changes → leave the existing credential_id.
      let credentialId: number | null | undefined;
      if (values.anonymous) {
        credentialId = null;
      } else if (values.credential_secret) {
        const credentialType = (values.credential_type ?? allowedCredentialTypes[0]) as
          | CredentialType
          | undefined;
        if (credentialType) {
          const created = await createCredential({
            name: `${name}-credential`,
            credential_type: credentialType,
            provider: domain,
            username: values.credential_username,
            secret: values.credential_secret,
            ssh_public_key: values.credential_ssh_public_key,
          }).unwrap();
          credentialId = created.id;
        } else {
          credentialId = null;
        }
      } else if (isEdit && provider) {
        credentialId = provider.credential_id;
      } else {
        credentialId = null;
      }

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
            credential_id: credentialId,
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
          subtype,
          category: values.category,
          direction: values.direction,
          label: values.label,
          description: values.description,
          base_url: values.base_url,
          config,
          credential_id: credentialId ?? null,
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
  ];

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
      title={isEdit ? `Edit provider: ${provider?.label}` : 'Create provider'}
      open={open}
      onCancel={onClose}
      width={640}
      destroyOnHidden
      footer={[
        isEdit ? (
          <Button
            key="test"
            icon={<PlayCircleOutlined />}
            loading={isTesting}
            disabled={isLoading}
            onClick={handleTest}
          >
            Test connection
          </Button>
        ) : null,
        <Button key="cancel" onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>,
        <Button key="save" type="primary" loading={isLoading} onClick={() => form.submit()}>
          {isEdit ? 'Save' : 'Create'}
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        {isEdit ? (
          <Form.Item label="Provider type">
            <Space>
              <Tag color="blue">{spec?.label ?? provider?.subtype}</Tag>
              <Typography.Text type="secondary">
                {spec ? DOMAIN_LABELS[spec.domain] : provider?.domain}
              </Typography.Text>
            </Space>
          </Form.Item>
        ) : (
          <>
            <Form.Item label="Provider type" required>
              <Radio.Group
                value={selectedDomain}
                onChange={(e) => handleDomainChange(e.target.value)}
                style={{ width: '100%' }}
              >
                <Flex gap={8} wrap>
                  {DOMAIN_ORDER.map((domain) => {
                    const hasSubtypes = availableTypes.some((t) => t.domain === domain);
                    if (!hasSubtypes) return null;
                    return (
                      <Radio.Button key={domain} value={domain}>
                        {DOMAIN_LABELS[domain]}
                      </Radio.Button>
                    );
                  })}
                </Flex>
              </Radio.Group>
            </Form.Item>

            {selectedDomain && domainSubtypes.length > 1 && (
              <Form.Item name="subtype" label="Provider subtype" rules={[{ required: true }]}>
                <Select
                  placeholder="Select subtype"
                  value={selectedSubtype}
                  onChange={setSelectedSubtype}
                  options={domainSubtypes.map((t) => ({ label: t.label, value: t.subtype }))}
                />
              </Form.Item>
            )}
          </>
        )}

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

        <Form.Item name="anonymous" label="Anonymous access" valuePropName="checked">
          <Switch />
        </Form.Item>

        <Form.Item noStyle shouldUpdate>
          {() => {
            const anonymous = form.getFieldValue('anonymous');
            if (anonymous || allowedCredentialTypes.length <= 1) return null;
            return (
              <Form.Item
                name="credential_type"
                label="Credential type"
                rules={[{ required: true }]}
              >
                <Select
                  options={allowedCredentialTypes.map((t) => ({
                    label: CREDENTIAL_TYPE_LABELS[t],
                    value: t,
                  }))}
                />
              </Form.Item>
            );
          }}
        </Form.Item>

        <Form.Item noStyle shouldUpdate>
          {() => {
            const anonymous = form.getFieldValue('anonymous');
            if (anonymous || allowedCredentialTypes.length === 0) return null;
            const credentialType = (form.getFieldValue('credential_type') ??
              allowedCredentialTypes[0]) as CredentialType | undefined;
            if (!credentialType) return null;
            return (
              <>
                {credentialType === 'https_basic' && (
                  <Form.Item
                    name="credential_username"
                    label="Username"
                    rules={[{ required: !isEdit }]}
                  >
                    <Input autoComplete="off" />
                  </Form.Item>
                )}
                <Form.Item
                  name="credential_secret"
                  label={secretLabel(credentialType)}
                  rules={[{ required: !isEdit }]}
                >
                  <Input.Password autoComplete="new-password" />
                </Form.Item>
                {credentialType === 'ssh_key' && (
                  <Form.Item name="credential_ssh_public_key" label="Public key">
                    <Input.TextArea rows={3} />
                  </Form.Item>
                )}
              </>
            );
          }}
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
