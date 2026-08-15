/**
 * @file Settings/Providers/DeleteProviderModal.tsx
 * @description Delete confirmation modal. Loads usage before opening: non-empty usage
 *              disables deletion; public/system providers require type-to-confirm.
 * @dependencies antd, RTK Query
 * @relatedFiles ./index.tsx
 */

import { useEffect, useState } from 'react';
import { Alert, App, Flex, Input, Modal, Spin, Table, Typography } from 'antd';
import { useDeleteProviderMutation, useGetProviderUsageQuery } from '../../../store/api';
import type { ProviderUsageItem, ResourceProvider } from '../../../types';

interface DeleteProviderModalProps {
  provider?: ResourceProvider;
  onClose: () => void;
}

export function DeleteProviderModal({ provider, onClose }: DeleteProviderModalProps) {
  const { message } = App.useApp();
  const [deleteProvider, { isLoading }] = useDeleteProviderMutation();
  const [confirmText, setConfirmText] = useState('');

  const { data: usage, isLoading: usageLoading } = useGetProviderUsageQuery(provider?.id ?? 0, {
    skip: !provider,
  });

  const isProtected = provider?.is_protected;
  const requiresTypeConfirm = provider?.category === 'public' || provider?.category === 'system';
  const usageItems = (usage?.usage ?? []) as ProviderUsageItem[];
  const hasUsage = usageItems.length > 0;
  const canDelete =
    !isProtected && !hasUsage && (!requiresTypeConfirm || confirmText === provider?.label);

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
        {isProtected && (
          <Alert type="warning" title="Провайдер защищён и не может быть удалён" showIcon />
        )}

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
            {requiresTypeConfirm
              ? 'Введите имя провайдера для подтверждения удаления.'
              : 'Удаление провайдера необратимо.'}
          </Typography.Text>
        )}

        {requiresTypeConfirm && !hasUsage && !isProtected && (
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

export default DeleteProviderModal;
