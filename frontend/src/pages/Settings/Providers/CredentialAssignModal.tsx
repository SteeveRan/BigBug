/**
 * @file Settings/Providers/CredentialAssignModal.tsx
 * @description Assign an existing compatible credential to a provider (PATCH credential_id).
 * @dependencies antd, RTK Query
 * @relatedFiles ./index.tsx, ./ProviderFormModal.tsx
 */

import { useMemo, useState } from 'react';
import { App, Button, Flex, Modal, Select } from 'antd';
import {
  useGetCredentialsQuery,
  useGetProviderTypesQuery,
  useUpdateProviderMutation,
} from '../../../store/api';
import type { CredentialDetail, ProviderTypeSpec, ResourceProvider } from '../../../types';

interface CredentialAssignModalProps {
  provider?: ResourceProvider;
  onClose: () => void;
}

export function CredentialAssignModal({ provider, onClose }: CredentialAssignModalProps) {
  const { message } = App.useApp();
  const { data: credentials = [] } = useGetCredentialsQuery();
  const { data: types = [] } = useGetProviderTypesQuery();
  const [updateProvider, { isLoading }] = useUpdateProviderMutation();
  const [credentialId, setCredentialId] = useState<number | undefined>(undefined);

  const allowedTypes = useMemo(() => {
    const spec = (types as ProviderTypeSpec[]).find((t) => t.subtype === provider?.subtype);
    return spec?.allowed_credential_types ?? [];
  }, [types, provider]);

  const options = useMemo(
    () =>
      (credentials as CredentialDetail[])
        .filter((c) => allowedTypes.includes(c.credential_type))
        .map((c) => ({ label: c.name, value: c.id })),
    [credentials, allowedTypes]
  );

  const handleSave = async () => {
    if (!provider || credentialId === undefined) return;
    try {
      await updateProvider({ id: provider.id, data: { credential_id: credentialId } }).unwrap();
      message.success('Credential назначен');
      onClose();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Не удалось назначить credential');
    }
  };

  return (
    <Modal
      title={`Assign credential: ${provider?.label ?? ''}`}
      open={!!provider}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button
          key="save"
          type="primary"
          onClick={handleSave}
          disabled={credentialId === undefined}
          loading={isLoading}
        >
          Assign
        </Button>,
      ]}
    >
      <Flex vertical gap={12}>
        <Select
          placeholder="Select compatible credential"
          value={credentialId}
          onChange={setCredentialId}
          options={options}
          notFoundContent="No compatible credentials"
          style={{ width: '100%' }}
        />
      </Flex>
    </Modal>
  );
}

export default CredentialAssignModal;
