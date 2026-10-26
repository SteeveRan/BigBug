/**
 * @file Settings/Authentication/ProviderFormModal.tsx
 * @description Modal form for creating/editing a single OIDC provider.
 *              Reuses the field layout of the former singleton settings form.
 * @dependencies antd, ../../store/api, ../../types
 * @relatedFiles ../index.tsx (provider list page)
 */

import { useEffect, useMemo, useState } from 'react';
import {
  Modal,
  Input,
  Switch,
  Typography,
  InputNumber,
  Flex,
  Divider,
  Table,
  Button,
  Tooltip,
  App,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

import type { OIDCProvider, OIDCProviderUpdate } from '../../../types';
import { useCreateOidcProviderMutation, useUpdateOidcProviderMutation } from '../../../store/api';

const MASKED_SECRET = '********';
const SECRET_PLACEHOLDER = 'Enter new secret to change';

interface RoleMappingEntry {
  id: number; // local id for React key
  providerRole: string;
  bigbugRole: string;
}

let nextMappingId = 0;

function createMappingEntry(providerRole = '', bigbugRole = ''): RoleMappingEntry {
  return { id: ++nextMappingId, providerRole, bigbugRole };
}

function recordToEntries(rm: Record<string, string> | undefined | null): RoleMappingEntry[] {
  if (!rm || Object.keys(rm).length === 0) return [];
  return Object.entries(rm).map(([providerRole, bigbugRole]) => ({
    id: ++nextMappingId,
    providerRole,
    bigbugRole,
  }));
}

function entriesToRecord(entries: RoleMappingEntry[]): Record<string, string> {
  const record: Record<string, string> = {};
  for (const entry of entries) {
    const key = entry.providerRole.trim();
    if (key) {
      record[key] = entry.bigbugRole.trim();
    }
  }
  return record;
}

interface ProviderFormModalProps {
  open: boolean;
  /** Provider being edited; null → create mode. */
  provider: OIDCProvider | null;
  /** Next sort_order suggestion for new providers. */
  nextSortOrder: number;
  onClose: () => void;
}

export function ProviderFormModal({
  open,
  provider,
  nextSortOrder,
  onClose,
}: ProviderFormModalProps) {
  const { message } = App.useApp();
  const [createProvider, { isLoading: isCreating }] = useCreateOidcProviderMutation();
  const [updateProvider, { isLoading: isSaving }] = useUpdateOidcProviderMutation();
  const isSavingAny = isCreating || isSaving;

  const [name, setName] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [issuerUrl, setIssuerUrl] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [frontendClientId, setFrontendClientId] = useState('');
  const [publicUrl, setPublicUrl] = useState('');
  const [sortOrder, setSortOrder] = useState(0);
  const [mappings, setMappings] = useState<RoleMappingEntry[]>([]);
  const [secretWasMasked, setSecretWasMasked] = useState(false);
  const [touched, setTouched] = useState(false);

  // Populate form when the modal opens for a provider (or reset for create).
  useEffect(() => {
    if (!open) return;
    setTouched(false);
    if (provider) {
      const isMasked = provider.client_secret === MASKED_SECRET;
      setName(provider.name);
      setEnabled(provider.enabled);
      setIssuerUrl(provider.issuer_url ?? '');
      setClientId(provider.client_id ?? '');
      setClientSecret(isMasked ? '' : provider.client_secret);
      setSecretWasMasked(isMasked);
      setFrontendClientId(provider.frontend_client_id ?? '');
      setPublicUrl(provider.public_url ?? '');
      setSortOrder(provider.sort_order);
      setMappings(recordToEntries(provider.role_mapping));
    } else {
      setName('');
      setEnabled(true);
      setIssuerUrl('');
      setClientId('');
      setClientSecret('');
      setSecretWasMasked(false);
      setFrontendClientId('');
      setPublicUrl('');
      setSortOrder(nextSortOrder);
      setMappings([]);
    }
  }, [open, provider, nextSortOrder]);

  const canSubmit = useMemo(
    () => name.trim() !== '' && issuerUrl.trim() !== '' && clientId.trim() !== '',
    [name, issuerUrl, clientId]
  );

  const extractError = (err: unknown, fallback: string): string => {
    if (err && typeof err === 'object' && 'data' in err) {
      const data = (err as { data?: { detail?: unknown } }).data;
      if (typeof data?.detail === 'string') return data.detail;
      // FastAPI 422 validation errors: detail is a list of {msg, loc}
      if (Array.isArray(data?.detail)) {
        const first = data.detail[0] as { msg?: string } | undefined;
        if (first?.msg) return first.msg;
      }
    }
    return fallback;
  };

  const handleSave = async () => {
    try {
      if (provider) {
        const payload: OIDCProviderUpdate = {
          name: name.trim(),
          issuer_url: issuerUrl.trim(),
          client_id: clientId.trim(),
        };
        if (!provider.enabled || enabled !== provider.enabled) payload.enabled = enabled;
        if (clientSecret !== '') payload.client_secret = clientSecret;
        payload.frontend_client_id = frontendClientId.trim();
        payload.public_url = publicUrl.trim() || null;
        payload.sort_order = sortOrder;
        payload.role_mapping = entriesToRecord(mappings);
        await updateProvider({ id: provider.id, data: payload }).unwrap();
        message.success('Provider saved successfully');
      } else {
        await createProvider({
          name: name.trim(),
          issuer_url: issuerUrl.trim(),
          client_id: clientId.trim(),
          client_secret: clientSecret || undefined,
          frontend_client_id: frontendClientId.trim() || undefined,
          enabled,
          public_url: publicUrl.trim() || null,
          role_mapping: entriesToRecord(mappings),
          sort_order: sortOrder,
        }).unwrap();
        message.success('Provider created successfully');
      }
      onClose();
    } catch (err: unknown) {
      message.error(extractError(err, 'Failed to save provider'));
    }
  };

  const mappingColumns: ColumnsType<RoleMappingEntry> = [
    {
      title: 'Provider Role',
      key: 'providerRole',
      render: (_: unknown, record: RoleMappingEntry) => (
        <Input
          size="small"
          value={record.providerRole}
          onChange={(e) =>
            setMappings((prev) =>
              prev.map((m) => (m.id === record.id ? { ...m, providerRole: e.target.value } : m))
            )
          }
          placeholder="e.g. bigbug-admin"
          disabled={isSavingAny}
          aria-label={`Provider role for mapping ${record.id}`}
        />
      ),
    },
    {
      title: 'BigBug Role',
      key: 'bigbugRole',
      render: (_: unknown, record: RoleMappingEntry) => (
        <Input
          size="small"
          value={record.bigbugRole}
          onChange={(e) =>
            setMappings((prev) =>
              prev.map((m) => (m.id === record.id ? { ...m, bigbugRole: e.target.value } : m))
            )
          }
          placeholder="e.g. admin"
          disabled={isSavingAny}
          aria-label={`BigBug role for mapping ${record.id}`}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 60,
      align: 'right',
      render: (_: unknown, record: RoleMappingEntry) => (
        <Tooltip title="Remove mapping">
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => setMappings((prev) => prev.filter((m) => m.id !== record.id))}
            disabled={isSavingAny}
            aria-label={`Remove mapping ${record.providerRole || '(empty)'}`}
          />
        </Tooltip>
      ),
    },
  ];

  return (
    <Modal
      title={provider ? `Edit Provider: ${provider.name}` : 'Add OIDC Provider'}
      open={open}
      onOk={handleSave}
      onCancel={onClose}
      okText="Save"
      okButtonProps={{ disabled: !canSubmit || isSavingAny, loading: isSavingAny }}
      destroyOnHidden
      width={720}
    >
      <Flex vertical gap={12}>
        <Flex wrap="wrap" gap={16}>
          <div style={{ flexGrow: 1, flexShrink: 1, flexBasis: 300, minWidth: 260 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Display Name</Typography.Text>
            </div>
            <Input
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setTouched(true);
              }}
              placeholder="e.g. Corporate Keycloak"
              disabled={isSavingAny}
              aria-label="Provider display name"
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Shown on the login button ("Sign in with …")
            </Typography.Text>
          </div>
          <div style={{ flexGrow: 0, flexShrink: 1, flexBasis: 160 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Sort Order</Typography.Text>
            </div>
            <InputNumber
              value={sortOrder}
              onChange={(v) => setSortOrder(typeof v === 'number' ? v : 0)}
              min={0}
              style={{ width: '100%' }}
              disabled={isSavingAny}
              aria-label="Provider sort order"
            />
          </div>
        </Flex>

        <div>
          <Typography.Text style={{ fontSize: 12 }}>Issuer URL</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
            Full issuer URI (RFC 8414), including /realms/&lt;realm&gt;
          </Typography.Text>
          <Input
            value={issuerUrl}
            onChange={(e) => setIssuerUrl(e.target.value)}
            placeholder="https://kc.example.com/realms/myrealm"
            disabled={isSavingAny}
            status={
              touched && issuerUrl.trim() !== '' && !issuerUrl.includes('/realms/')
                ? 'warning'
                : undefined
            }
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            The OIDC issuer URL of your authentication provider
          </Typography.Text>
        </div>

        <Flex wrap="wrap" gap={16}>
          <div style={{ flexGrow: 1, flexShrink: 1, flexBasis: 300, minWidth: 260 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Public URL</Typography.Text>
            </div>
            <Input
              value={publicUrl}
              onChange={(e) => setPublicUrl(e.target.value)}
              placeholder="https://auth.example.com"
              disabled={isSavingAny}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Optional. Public-facing URL for the auth provider (if different from issuer)
            </Typography.Text>
          </div>
          <div style={{ flexGrow: 1, flexShrink: 1, flexBasis: 300, minWidth: 260 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Backend Client ID</Typography.Text>
            </div>
            <Input
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="bigbug-backend"
              disabled={isSavingAny}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              OIDC client ID for backend server-to-server communication
            </Typography.Text>
          </div>
        </Flex>

        <Flex wrap="wrap" gap={16}>
          <div style={{ flexGrow: 1, flexShrink: 1, flexBasis: 300, minWidth: 260 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Frontend Client ID</Typography.Text>
            </div>
            <Input
              value={frontendClientId}
              onChange={(e) => setFrontendClientId(e.target.value)}
              placeholder="bigbug-frontend"
              disabled={isSavingAny}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              OIDC client ID for frontend SPA (public client)
            </Typography.Text>
          </div>
          <div style={{ flexGrow: 1, flexShrink: 1, flexBasis: 300, minWidth: 260 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Client Secret</Typography.Text>
            </div>
            <Input.Password
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder={secretWasMasked ? SECRET_PLACEHOLDER : ''}
              disabled={isSavingAny}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {secretWasMasked
                ? 'Secret is stored. Enter a new value to change.'
                : 'OIDC client secret (confidential client)'}
            </Typography.Text>
          </div>
        </Flex>

        <Flex align="center" gap={8}>
          <Switch
            checked={enabled}
            onChange={setEnabled}
            disabled={isSavingAny}
            aria-label="Enable provider"
          />
          <Typography.Text>{enabled ? 'Enabled' : 'Disabled'}</Typography.Text>
        </Flex>

        <Divider />
        <Typography.Text type="secondary">
          Map provider roles (from your OIDC provider) to BigBug internal roles.
        </Typography.Text>
        <Button
          icon={<PlusOutlined />}
          onClick={() => setMappings((prev) => [...prev, createMappingEntry()])}
          disabled={isSavingAny}
        >
          Add Mapping
        </Button>
        {mappings.length > 0 && (
          <Table
            columns={mappingColumns}
            dataSource={mappings}
            rowKey="id"
            pagination={false}
            size="small"
          />
        )}
      </Flex>
    </Modal>
  );
}

export default ProviderFormModal;
