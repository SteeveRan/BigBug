/**
 * @file api/status.ts
 * @description Public status endpoints (unauthenticated). Used by the global
 *              MaintenanceBanner — must not trigger 401-logout handling.
 * @dependencies api/base.ts
 */

import { api } from './base';

export const statusApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getMaintenanceStatus: builder.query<{ maintenance_mode: boolean }, void>({
      query: () => '/status/maintenance',
    }),
  }),
});

export const { useGetMaintenanceStatusQuery } = statusApi;
