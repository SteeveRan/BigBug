/**
 * @file MaintenanceBanner/index.tsx
 * @description Global persistent banner shown when maintenance mode is on.
 *              Hidden (renders nothing) while the first poll is in flight or
 *              when maintenance is off — no layout shift, no flash.
 * @dependencies antd, ../../hooks/useMaintenanceMode
 * @relatedFiles ../../hooks/useMaintenanceMode.ts, ../../App.tsx
 */

import { Alert } from 'antd';
import { useMaintenanceMode } from '../../hooks/useMaintenanceMode';

export function MaintenanceBanner() {
  const maintenanceMode = useMaintenanceMode();
  if (!maintenanceMode) return null;

  return (
    <Alert
      banner
      type="warning"
      showIcon
      title="Идут технические работы — фоновая синхронизация приостановлена"
    />
  );
}
