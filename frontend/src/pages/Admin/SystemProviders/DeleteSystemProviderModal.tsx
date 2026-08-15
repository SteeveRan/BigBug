/**
 * @file Admin/SystemProviders/DeleteSystemProviderModal.tsx
 * @description Delete confirmation modal for system providers. Unlike the general
 *              Settings→Providers modal, deletion is not blocked by `is_protected`
 *              (the admin with `providers_system:write` is allowed), but it still
 *              blocks when the provider has dependent resources and requires
 *              type-to-confirm for the system category.
 * @dependencies antd, RTK Query
 * @relatedFiles ./index.tsx
 */

import { useEffect, useState } from 'react';
import { Alert, App, Flex, Input, Modal, Spin, Table, Typography } from 'antd';
import { useDeleteProviderMutation, useGetProviderUsageQuery } from '../../../store/api';
import type { ProviderUsageItem, ResourceProvider } from '../../../types';

interface DeleteSystemProviderModalProps {
  provider?: ResourceProvider;
  onClose: () => void;
}

export function DeleteSystemProviderModal({ provider, onClose }: DeleteSystemProviderModalProps) {
  const { message } = App.useApp();
  const [deleteProvider, { isLoading }] = useDeleteProviderMutation();
  const [confirmText, setConfirmText] = useState('');

  const { data: usage, isLoading: usageLoading } = useGetProviderUsageQuery(provider?.id ?? 0, {
    skip: !provider,
  });

  const usageItems = (usage?.usage ?? []) as ProviderUsageItem[];
  const hasUsage = usageItems.length > 0;
  const canDelete = !hasUsage && confirmText === provider?.label;

  useEffect(() => {
    setConfirmText('');
  }, [provider]);

  const handleDelete = async () => {
    if (!provider || !canDelete) return;
    try {
      await deleteProvider(provider.id).unwrap();
      message.success('Провайдер удалён');
      onClose();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Не удалось удалить провайдера');
    }
  };

  return (
    <Modal
      title={`Delete provider: ${provider?.label ?? ''}`}
      open={!!provider}
      onCancel={onClose}
      onOk={handleDelete}
      okButtonProps={{ danger: true, disabled: !canDelete, loading: isLoading }}
      okText="Delete"
    >
      <Flex vertical gap={12}>
        {usageLoading ? (
          <Flex justify="center" style={{ padding: '16px 0' }}>
            <Spin />
          </Flex>
        ) : hasUsage ? (
          <>
            <Alert
              type="warning"
              title="Провайдер используется"
              description="Удаление невозможно, пока существуют зависимые ресурсы."
              showIcon
            />
            <Table
              size="small"
              rowKey="resource"
              pagination={false}
              dataSource={usageItems}
              columns={[
                { title: 'Resource', dataIndex: 'resource', key: 'resource' },
                { title: 'Count', dataIndex: 'count', key: 'count', width: 100 },
              ]}
            />
          </>
        ) : (
          <Typography.Text type="secondary">
            Введите имя провайдера для подтверждения удаления.
          </Typography.Text>
        )}

        {!hasUsage && (
          <Input
            placeholder={provider?.label}
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
          />
        )}
      </Flex>
    </Modal>
  );
}

export default DeleteSystemProviderModal;
