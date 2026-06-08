/**
 * @file Settings/Authentication/index.tsx
 * @description Settings page for managing OIDC/SSO authentication configuration.
 *              Provides UI for configuring Keycloak/SSO issuer, client credentials,
 *              and role mapping between provider roles and BigBug roles.
 * @dependencies antd, @ant-design/icons, ../../store/api, ../../components/PermissionGate
 * @relatedFiles ../../store/api.ts, ../../types/index.ts, ../../components/PermissionGate.tsx
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Spin,
  Divider,
  Input,
  Switch,
  Tooltip,
  App,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

import type { OIDCConfigUpdate } from '../../../types';
import { useGetOidcConfigQuery, useUpdateOidcConfigMutation } from '../../../store/api';

// ─── Constants ───────────────────────────────────────────────────────────────

const MASKED_SECRET = '********';
const SECRET_PLACEHOLDER = 'Enter new secret to change';

// ─── Role mapping entry ──────────────────────────────────────────────────────

interface RoleMappingEntry {
  id: number; // local id for React key
  providerRole: string;
  bigbugRole: string;
}

let nextMappingId = 0;

function createMappingEntry(providerRole = '', bigbugRole = ''): RoleMappingEntry {
  return { id: ++nextMappingId, providerRole, bigbugRole };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Convert Record<string, string> to RoleMappingEntry[] */
function recordToEntries(rm: Record<string, string> | undefined | null): RoleMappingEntry[] {
  if (!rm || Object.keys(rm).length === 0) return [];
  return Object.entries(rm).map(([providerRole, bigbugRole]) => ({
    id: ++nextMappingId,
    providerRole,
    bigbugRole,
  }));
}

/** Convert RoleMappingEntry[] to Record<string, string> */
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

// ─── Main component ──────────────────────────────────────────────────────────

export function AuthenticationSettings() {
  const { message } = App.useApp();
  const { data: config, isLoading, isError } = useGetOidcConfigQuery();
  const [updateConfig, { isLoading: isSaving }] = useUpdateOidcConfigMutation();

  // Form state
  const [enabled, setEnabled] = useState(false);
  const [issuerUrl, setIssuerUrl] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [frontendClientId, setFrontendClientId] = useState('');
  const [publicUrl, setPublicUrl] = useState('');
  const [mappings, setMappings] = useState<RoleMappingEntry[]>([]);

  // Track whether the secret was masked (so we know user hasn't changed it)
  const [secretWasMasked, setSecretWasMasked] = useState(false);

  // Track original values for dirty detection
  const [originalValues, setOriginalValues] = useState<{
    enabled: boolean;
    issuerUrl: string;
    clientId: string;
    clientSecret: string;
    frontendClientId: string;
    publicUrl: string;
    mappingsJson: string;
  } | null>(null);

  // Populate form when data loads
  useEffect(() => {
    if (!config) return;

    const secretValue = config.client_secret === MASKED_SECRET ? '' : config.client_secret;
    const isMasked = config.client_secret === MASKED_SECRET;

    setEnabled(config.enabled);
    setIssuerUrl(config.issuer_url ?? '');
    setClientId(config.client_id ?? '');
    setClientSecret(secretValue);
    setSecretWasMasked(isMasked);
    setFrontendClientId(config.frontend_client_id ?? '');
    setPublicUrl(config.public_url ?? '');
    setMappings(recordToEntries(config.role_mapping));

    setOriginalValues({
      enabled: config.enabled,
      issuerUrl: config.issuer_url ?? '',
      clientId: config.client_id ?? '',
      clientSecret: secretValue,
      frontendClientId: config.frontend_client_id ?? '',
      publicUrl: config.public_url ?? '',
      mappingsJson: JSON.stringify(config.role_mapping ?? {}),
    });
  }, [config]);

  // Dirty detection
  const isDirty = useMemo(() => {
    if (!originalValues) return false;
    return (
      originalValues.enabled !== enabled ||
      originalValues.issuerUrl !== issuerUrl ||
      originalValues.clientId !== clientId ||
      originalValues.clientSecret !== clientSecret ||
      originalValues.frontendClientId !== frontendClientId ||
      originalValues.publicUrl !== publicUrl ||
      originalValues.mappingsJson !== JSON.stringify(entriesToRecord(mappings))
    );
  }, [
    originalValues,
    enabled,
    issuerUrl,
    clientId,
    clientSecret,
    frontendClientId,
    publicUrl,
    mappings,
  ]);

  const showMessage = useCallback(
    (msg: string, severity: 'success' | 'error') => {
      if (severity === 'success') {
        message.success(msg);
      } else {
        message.error(msg);
      }
    },
    [message],
  );

  // ─── Role mapping handlers ─────────────────────────────────────────────────

  const handleAddMapping = () => {
    setMappings((prev) => [...prev, createMappingEntry()]);
  };

  const handleRemoveMapping = (id: number) => {
    setMappings((prev) => prev.filter((m) => m.id !== id));
  };

  const handleMappingChange = (id: number, field: 'providerRole' | 'bigbugRole', value: string) => {
    setMappings((prev) => prev.map((m) => (m.id === id ? { ...m, [field]: value } : m)));
  };

  // ─── Submit handler ────────────────────────────────────────────────────────

  const handleSave = async () => {
    const payload: OIDCConfigUpdate = {};

    if (originalValues?.enabled !== enabled) {
      payload.enabled = enabled;
    }

    if (originalValues?.issuerUrl !== issuerUrl) {
      payload.issuer_url = issuerUrl;
    }

    if (originalValues?.clientId !== clientId) {
      payload.client_id = clientId;
    }

    // Only send client_secret if user actually typed something
    if (clientSecret !== '') {
      payload.client_secret = clientSecret;
    }

    if (originalValues?.frontendClientId !== frontendClientId) {
      payload.frontend_client_id = frontendClientId;
    }

    if (originalValues?.publicUrl !== publicUrl) {
      payload.public_url = publicUrl || null;
    }

    const currentMappings = entriesToRecord(mappings);
    if (originalValues?.mappingsJson !== JSON.stringify(currentMappings)) {
      payload.role_mapping = currentMappings;
    }

    // Don't send empty update
    if (Object.keys(payload).length === 0) return;

    try {
      await updateConfig(payload).unwrap();
      showMessage('Settings saved successfully', 'success');

      // Update original values after successful save
      setOriginalValues({
        enabled,
        issuerUrl,
        clientId,
        clientSecret,
        frontendClientId,
        publicUrl,
        mappingsJson: JSON.stringify(entriesToRecord(mappings)),
      });
      setSecretWasMasked(false);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to save settings')
          : 'Failed to save settings';
      showMessage(msg, 'error');
    }
  };

  // ─── Table columns for role mappings ───────────────────────────────────────

  const mappingColumns: ColumnsType<RoleMappingEntry> = [
    {
      title: 'Provider Role',
      key: 'providerRole',
      render: (_: unknown, record: RoleMappingEntry) => (
        <Input
          size="small"
          value={record.providerRole}
          onChange={(e) => handleMappingChange(record.id, 'providerRole', e.target.value)}
          placeholder="e.g. bigbug-admin"
          disabled={isSaving}
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
          onChange={(e) => handleMappingChange(record.id, 'bigbugRole', e.target.value)}
          placeholder="e.g. admin"
          disabled={isSaving}
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
            onClick={() => handleRemoveMapping(record.id)}
            disabled={isSaving}
            aria-label={`Remove mapping ${record.providerRole || '(empty)'}`}
          />
        </Tooltip>
      ),
    },
  ];

  // ─── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: '64px 0' }}>
        <Spin />
      </Flex>
    );
  }

  if (isError) {
    return (
      <Flex vertical gap={16}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Authentication Settings
        </Typography.Title>
        <Typography.Text type="danger">
          Failed to load authentication configuration. Please try again later.
        </Typography.Text>
      </Flex>
    );
  }

  return (
    <Flex vertical gap={16}>
      <div>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Authentication Settings
        </Typography.Title>
        <Typography.Text type="secondary">
          Configure OIDC / SSO authentication provider (Keycloak) and role mapping between external
          roles and BigBug internal roles.
        </Typography.Text>
      </div>

      {/* ── OIDC / SSO Configuration Section ─────────────────────────────── */}
      <Card
        title="OIDC / SSO Configuration"
        extra={
          <Flex align="center" gap={8}>
            <Typography.Text>{enabled ? 'Enabled' : 'Disabled'}</Typography.Text>
            <Switch
              checked={enabled}
              onChange={(checked) => setEnabled(checked)}
              aria-label="Enable SSO / OIDC"
            />
          </Flex>
        }
      >
        <Flex wrap="wrap" gap={16}>
          <div style={{ flex: '1 1 360px', minWidth: 280 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Issuer URL</Typography.Text>
            </div>
            <Input
              value={issuerUrl}
              onChange={(e) => setIssuerUrl(e.target.value)}
              placeholder="https://keycloak.example.com/realms/myrealm"
              disabled={isSaving}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              The OIDC issuer URL of your authentication provider
            </Typography.Text>
          </div>

          <div style={{ flex: '1 1 360px', minWidth: 280 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Public URL</Typography.Text>
            </div>
            <Input
              value={publicUrl}
              onChange={(e) => setPublicUrl(e.target.value)}
              placeholder="https://auth.example.com"
              disabled={isSaving}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Optional. Public-facing URL for the auth provider (if different from issuer)
            </Typography.Text>
          </div>

          <div style={{ flex: '1 1 360px', minWidth: 280 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Backend Client ID</Typography.Text>
            </div>
            <Input
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="bigbug-backend"
              disabled={isSaving}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              OIDC client ID for backend server-to-server communication
            </Typography.Text>
          </div>

          <div style={{ flex: '1 1 360px', minWidth: 280 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Frontend Client ID</Typography.Text>
            </div>
            <Input
              value={frontendClientId}
              onChange={(e) => setFrontendClientId(e.target.value)}
              placeholder="bigbug-frontend"
              disabled={isSaving}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              OIDC client ID for frontend SPA (public client)
            </Typography.Text>
          </div>

          <div style={{ flex: '1 1 360px', minWidth: 280 }}>
            <div style={{ marginBottom: 4 }}>
              <Typography.Text style={{ fontSize: 12 }}>Client Secret</Typography.Text>
            </div>
            <Input.Password
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder={secretWasMasked ? SECRET_PLACEHOLDER : ''}
              disabled={isSaving}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {secretWasMasked
                ? 'Secret is stored. Enter a new value to change.'
                : 'OIDC client secret (confidential client)'}
            </Typography.Text>
          </div>
        </Flex>
      </Card>

      {/* ── Role Mapping Section ─────────────────────────────────────────── */}
      <Card
        title="Role Mapping"
        extra={
          <Button
            icon={<PlusOutlined />}
            onClick={handleAddMapping}
            disabled={isSaving}
          >
            Add Mapping
          </Button>
        }
      >
        <Typography.Text type="secondary">
          Map provider roles (from your OIDC provider) to BigBug internal roles.
        </Typography.Text>

        <Divider />

        {mappings.length === 0 ? (
          <Typography.Text
            type="secondary"
            style={{
              display: 'block',
              padding: '16px 0',
              textAlign: 'center',
              fontStyle: 'italic',
            }}
          >
            No role mappings configured. Add a mapping to map external roles to BigBug roles.
          </Typography.Text>
        ) : (
          <Table
            columns={mappingColumns}
            dataSource={mappings}
            rowKey="id"
            pagination={false}
            size="small"
          />
        )}
      </Card>

      {/* ── Save Button ──────────────────────────────────────────────────── */}
      <Flex justify="flex-end">
        <Button
          type="primary"
          size="large"
          onClick={handleSave}
          disabled={!isDirty || isSaving}
          loading={isSaving}
        >
          Save Changes
        </Button>
      </Flex>
    </Flex>
  );
}

export default AuthenticationSettings;
