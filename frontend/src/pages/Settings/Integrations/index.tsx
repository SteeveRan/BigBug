/**
 * @file Settings/Integrations/index.tsx
 * @description Settings page for managing integration instances (GitLab, Harbor, GitHub, Docker Registry, Helm Repository).
 *              Uses Ant Design Tabs, Tables, Modals for CRUD operations and connection testing.
 * @dependencies antd, @ant-design/icons, ../../store/api, ../../components/StatusChip
 * @relatedFiles ../../store/api.ts, ../../types/index.ts, ../../components/PermissionGate.tsx
 */

import { useState, useCallback } from 'react';
import { Typography, Flex, App, Tabs } from 'antd';
import { TAB_LABELS } from './common';
import { GitlabPanel } from './Gitlab';
import { HarborPanel } from './Harbor';
import { GithubPanel } from './Github';
import { DockerRegistryPanel } from './DockerRegistry';
import { HelmRepositoryPanel } from './HelmRepository';

// ─── Main component ──────────────────────────────────────────────────────────

export function SettingsIntegrations() {
  const { message } = App.useApp();
  const [tabIndex, setTabIndex] = useState(0);

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

  return (
    <Flex vertical gap={16}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        Settings
      </Typography.Title>

      <Tabs
        activeKey={String(tabIndex)}
        onChange={(key) => setTabIndex(Number(key))}
        items={TAB_LABELS.map((label, i) => ({
          key: String(i),
          label,
          children:
            i === 0 ? (
              <GitlabPanel showMessage={showMessage} />
            ) : i === 1 ? (
              <HarborPanel showMessage={showMessage} />
            ) : i === 2 ? (
              <GithubPanel showMessage={showMessage} />
            ) : i === 3 ? (
              <DockerRegistryPanel showMessage={showMessage} />
            ) : (
              <HelmRepositoryPanel showMessage={showMessage} />
            ),
        }))}
      />
    </Flex>
  );
}

export default SettingsIntegrations;
