/**
 * @file Settings/Providers/ShareProviderModal.tsx
 * @description Share a private provider with one of the caller's teams (POST /providers/{id}/share).
 * @dependencies antd, RTK Query
 * @relatedFiles ./index.tsx
 */

import { useMemo, useState } from 'react';
import { Alert, App, Button, Flex, Modal, Select } from 'antd';
import { useGetTeamsQuery, useShareProviderMutation } from '../../../store/api';
import type { ResourceProvider, Team } from '../../../types';

interface ShareProviderModalProps {
  provider?: ResourceProvider;
  onClose: () => void;
}

export function ShareProviderModal({ provider, onClose }: ShareProviderModalProps) {
  const { message } = App.useApp();
  const { data: teams = [] } = useGetTeamsQuery();
  const [shareProvider, { isLoading }] = useShareProviderMutation();
  const [teamId, setTeamId] = useState<number | undefined>(undefined);

  const options = useMemo(
    () => (teams as Team[]).map((t) => ({ label: t.name, value: t.id })),
    [teams]
  );

  const handleShare = async () => {
    if (!provider || teamId === undefined) return;
    try {
      await shareProvider({ id: provider.id, team_id: teamId }).unwrap();
      message.success('Провайдер открыт для команды');
      onClose();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Не удалось поделиться провайдером');
    }
  };

  return (
    <Modal
      title={`Share provider: ${provider?.label ?? ''}`}
      open={!!provider}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button
          key="share"
          type="primary"
          onClick={handleShare}
          disabled={teamId === undefined}
          loading={isLoading}
        >
          Share
        </Button>,
      ]}
    >
      <Flex vertical gap={12}>
        <Alert type="info" title="Провайдер станет виден всем участникам команды" showIcon />
        <Select
          placeholder="Select team"
          value={teamId}
          onChange={setTeamId}
          options={options}
          style={{ width: '100%' }}
          notFoundContent="No teams available"
        />
      </Flex>
    </Modal>
  );
}

export default ShareProviderModal;
