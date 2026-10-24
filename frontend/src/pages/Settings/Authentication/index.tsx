/**
 * @file Settings/Authentication/index.tsx
 * @description Settings page listing OIDC providers as cards. Each card shows
 *              name, issuer, enabled badge and sort_order with edit/delete/toggle
 *              actions; editing opens ProviderFormModal.
 * @dependencies antd, @ant-design/icons, ../../store/api, ./ProviderFormModal
 * @relatedFiles ./ProviderFormModal.tsx, ../../store/api.ts, ../../types/index.ts
 */

import { useState, useMemo } from 'react';
import { Card, Typography, Button, Flex, Spin, Tag, Popconfirm, App, Empty, Switch } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';

import type { OIDCProvider } from '../../../types';
import {
  useGetOidcProvidersQuery,
  useUpdateOidcProviderMutation,
  useDeleteOidcProviderMutation,
} from '../../../store/api';
import { ProviderFormModal } from './ProviderFormModal';

// ─── Main component ──────────────────────────────────────────────────────────

export function AuthenticationSettings() {
  const { message } = App.useApp();
  const { data: providers, isLoading, isError } = useGetOidcProvidersQuery();
  const [updateProvider, { isLoading: isToggling }] = useUpdateOidcProviderMutation();
  const [deleteProvider, { isLoading: isDeleting }] = useDeleteOidcProviderMutation();

  const [modalOpen, setModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<OIDCProvider | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const sorted = useMemo(
    () => [...(providers ?? [])].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id),
    [providers]
  );

  const nextSortOrder = useMemo(
    () => (sorted.length ? Math.max(...sorted.map((p) => p.sort_order)) + 1 : 0),
    [sorted]
  );

  const handleToggle = async (provider: OIDCProvider, enabled: boolean) => {
    try {
      await updateProvider({ id: provider.id, data: { enabled } }).unwrap();
      message.success(enabled ? 'Provider enabled' : 'Provider disabled');
    } catch {
      message.error('Failed to update provider');
    }
  };

  const handleDelete = async (provider: OIDCProvider) => {
    setDeletingId(provider.id);
    try {
      await deleteProvider(provider.id).unwrap();
      message.success('Provider deleted');
    } catch {
      message.error('Failed to delete provider');
    } finally {
      setDeletingId(null);
    }
  };

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
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Authentication Settings
          </Typography.Title>
          <Typography.Text type="secondary">
            Configure OIDC / SSO authentication providers. Each enabled provider renders a login
            button on the login page.
          </Typography.Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingProvider(null);
            setModalOpen(true);
          }}
        >
          Add Provider
        </Button>
      </Flex>

      {sorted.length === 0 ? (
        <Card>
          <Empty description="No OIDC providers configured. Add a provider to enable SSO login." />
        </Card>
      ) : (
        sorted.map((provider) => (
          <Card
            key={provider.id}
            title={
              <Flex align="center" gap={8}>
                <span>{provider.name}</span>
                <Tag color={provider.enabled ? 'success' : 'default'}>
                  {provider.enabled ? 'Enabled' : 'Disabled'}
                </Tag>
              </Flex>
            }
            extra={
              <Flex align="center" gap={8}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  sort: {provider.sort_order}
                </Typography.Text>
                <Switch
                  size="small"
                  checked={provider.enabled}
                  onChange={(checked) => handleToggle(provider, checked)}
                  disabled={isToggling}
                  aria-label={`Toggle provider ${provider.name}`}
                />
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => {
                    setEditingProvider(provider);
                    setModalOpen(true);
                  }}
                  aria-label={`Edit provider ${provider.name}`}
                >
                  Edit
                </Button>
                <Popconfirm
                  title="Delete provider?"
                  description={`SSO login via "${provider.name}" will stop working.`}
                  okText="Delete"
                  okButtonProps={{
                    danger: true,
                    loading: isDeleting && deletingId === provider.id,
                  }}
                  onConfirm={() => handleDelete(provider)}
                >
                  <Button
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    aria-label={`Delete provider ${provider.name}`}
                  />
                </Popconfirm>
              </Flex>
            }
          >
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Issuer
            </Typography.Text>
            <Typography.Paragraph style={{ marginBottom: 4 }} copyable>
              {provider.issuer_url || <em>not configured</em>}
            </Typography.Paragraph>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Client ID: {provider.client_id || '—'}
            </Typography.Text>
          </Card>
        ))
      )}

      <ProviderFormModal
        open={modalOpen}
        provider={editingProvider}
        nextSortOrder={nextSortOrder}
        onClose={() => setModalOpen(false)}
      />
    </Flex>
  );
}

export default AuthenticationSettings;
