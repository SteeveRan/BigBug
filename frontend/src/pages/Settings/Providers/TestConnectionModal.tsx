/**
 * @file Settings/Providers/TestConnectionModal.tsx
 * @description Modal that runs POST /providers/{id}/test and renders the result via StatusChip.
 * @dependencies antd, RTK Query, StatusChip
 * @relatedFiles ./index.tsx
 */

import { useEffect, useState } from 'react';
import { App, Button, Flex, Modal, Typography } from 'antd';
import { useTestProviderMutation } from '../../../store/api';
import type { ProviderTestResult, ResourceProvider } from '../../../types';
import { StatusChip } from '../../../components/StatusChip';

interface TestConnectionModalProps {
  provider?: ResourceProvider;
  onClose: () => void;
}

export function TestConnectionModal({ provider, onClose }: TestConnectionModalProps) {
  const { message } = App.useApp();
  const [testProvider, { isLoading }] = useTestProviderMutation();
  const [result, setResult] = useState<ProviderTestResult | undefined>(undefined);

  useEffect(() => {
    setResult(undefined);
    if (!provider) return;
    testProvider(provider.id)
      .unwrap()
      .then(setResult)
      .catch(() => setResult({ ok: false, status_flag: 1, status_text: 'Connection test failed' }));
  }, [provider, testProvider]);

  const retry = async () => {
    if (!provider) return;
    try {
      setResult(undefined);
      const res = await testProvider(provider.id).unwrap();
      setResult(res);
      if (res.ok) message.success('Подключение успешно');
    } catch {
      setResult({ ok: false, status_flag: 1, status_text: 'Connection test failed' });
    }
  };

  return (
    <Modal
      title={`Test: ${provider?.label ?? ''}`}
      open={!!provider}
      onCancel={onClose}
      footer={[
        <Button key="retry" type="primary" loading={isLoading} onClick={retry}>
          Retry
        </Button>,
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
      ]}
    >
      <Flex vertical gap={12} align="center" style={{ padding: '16px 0' }}>
        {isLoading ? (
          <Typography.Text type="secondary">Testing…</Typography.Text>
        ) : result ? (
          <>
            <StatusChip
              statusFlag={result.status_flag as 0 | 1 | 2 | 3 | 4}
              statusText={result.status_text}
            />
            {result.status_text && (
              <Typography.Text type="secondary">{result.status_text}</Typography.Text>
            )}
          </>
        ) : (
          <Typography.Text type="secondary">No result yet</Typography.Text>
        )}
      </Flex>
    </Modal>
  );
}

export default TestConnectionModal;
