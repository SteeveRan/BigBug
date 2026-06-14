/**
 * @file api/audit-logs.ts
 * @description Audit Logs endpoints
 * @dependencies api/base.ts
 */

import type { AuditLogList } from '../../types';
import { api } from './base';

export const auditLogsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getAuditLogs: builder.query<
      AuditLogList,
      {
        user_id?: number;
        action?: string;
        resource_type?: string;
        date_from?: string;
        date_to?: string;
        page?: number;
        page_size?: number;
      }
    >({
      query: (params) => ({ url: '/admin/audit-logs', params }),
      providesTags: ['AuditLog'],
    }),
  }),
});

export const {
  useGetAuditLogsQuery,
} = auditLogsApi;
