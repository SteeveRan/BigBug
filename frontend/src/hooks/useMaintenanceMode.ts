/**
 * @file useMaintenanceMode.ts
 * @description Exposes the platform maintenance-mode flag, polling the public
 *              /api/status/maintenance endpoint every 30 s. Works unauthenticated.
 * @dependencies ../store/api (useGetMaintenanceStatusQuery)
 * @relatedFiles ../components/MaintenanceBanner/index.tsx, ../store/api/status.ts
 */

import { useGetMaintenanceStatusQuery } from '../store/api';

const POLL_INTERVAL_MS = 30_000;

export function useMaintenanceMode(): boolean {
  const { data } = useGetMaintenanceStatusQuery(undefined, {
    pollingInterval: POLL_INTERVAL_MS,
  });
  return data?.maintenance_mode ?? false;
}
