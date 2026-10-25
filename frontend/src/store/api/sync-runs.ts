/**
 * @file api/sync-runs.ts
 * @description Admin sync-runs endpoints (issue #113): list + recovery actions
 *              (retry / retry-all-failed / requeue). Backend: /api/admin/sync-runs.
 * @dependencies api/base.ts
 */

import type { SyncRun } from '../../types';
import { api } from './base';

export interface SyncRunFilters {
  run_status?: string;
  entity_type?: string;
  entity_id?: number;
  stuck?: boolean;
}

export const syncRunsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getSyncRuns: builder.query<SyncRun[], SyncRunFilters | void>({
      query: (params) => ({
        url: '/admin/sync-runs',
        params: params ? { ...params, stuck: params.stuck || undefined } : undefined,
      }),
      providesTags: ['SyncRun'],
    }),
    retrySyncRun: builder.mutation<SyncRun, number>({
      query: (runId) => ({ url: `/admin/sync-runs/${runId}/retry`, method: 'POST' }),
      invalidatesTags: ['SyncRun'],
    }),
    retryAllFailed: builder.mutation<{ retried: number; total_failed_permanent: number }, void>({
      query: () => ({ url: '/admin/sync-runs/retry-all-failed', method: 'POST' }),
      invalidatesTags: ['SyncRun'],
    }),
    requeueSyncRun: builder.mutation<SyncRun, number>({
      query: (runId) => ({ url: `/admin/sync-runs/${runId}/requeue`, method: 'POST' }),
      invalidatesTags: ['SyncRun'],
    }),
  }),
});

export const {
  useGetSyncRunsQuery,
  useRetrySyncRunMutation,
  useRetryAllFailedMutation,
  useRequeueSyncRunMutation,
} = syncRunsApi;
