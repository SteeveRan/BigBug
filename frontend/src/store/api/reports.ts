/**
 * @file api/reports.ts
 * @description Reports endpoints (Duplicates, Storage, Status, Syncs, Bulk Operations)
 * @dependencies api/base.ts
 */

import type {
  DuplicatesReport,
  StorageReport,
  StorageRefreshStatus,
  StatusReport,
  SyncsReport,
  BulkOperationResponse,
} from '../../types';
import { api } from './base';

export const reportsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    // ── Duplicates ─────────────────────────────────────────────────

    getDuplicatesReport: builder.query<DuplicatesReport, void>({
      query: () => '/reports/duplicates',
      providesTags: ['Reports'],
    }),

    // ── Storage ───────────────────────────────────────────────────

    getStorageReport: builder.query<StorageReport, void>({
      query: () => '/reports/storage',
      providesTags: ['Reports'],
    }),
    refreshStorageReport: builder.mutation<StorageRefreshStatus, void>({
      query: () => ({ url: '/reports/storage/refresh', method: 'POST' }),
      invalidatesTags: ['Reports'],
    }),

    // ── Status ────────────────────────────────────────────────────

    getStatusReport: builder.query<StatusReport, { trend_days?: number } | void>({
      query: (params) => ({ url: '/reports/status', params: params ?? undefined }),
      providesTags: ['Reports'],
    }),

    // ── Syncs ─────────────────────────────────────────────────────

    getSyncsReport: builder.query<
      SyncsReport,
      { period_start?: string; period_end?: string } | void
    >({
      query: (params) => ({ url: '/reports/syncs', params: params ?? undefined }),
      providesTags: ['Reports'],
    }),

    // ── Bulk Operations ───────────────────────────────────────────

    bulkReassignSyncGroup: builder.mutation<
      BulkOperationResponse,
      { mirror_ids: number[]; sync_group_id: number }
    >({
      query: (body) => ({ url: '/reports/bulk/reassign-sync-group', method: 'POST', body }),
      invalidatesTags: ['Reports', 'Mirror', 'SyncGroup'],
    }),
    bulkChangeTargetGitlab: builder.mutation<
      BulkOperationResponse,
      { mirror_ids: number[]; sync_group_id: number }
    >({
      query: (body) => ({ url: '/reports/bulk/change-target-gitlab', method: 'POST', body }),
      invalidatesTags: ['Reports', 'Mirror', 'SyncGroup'],
    }),
    bulkApplyPipeline: builder.mutation<
      BulkOperationResponse,
      { mirror_ids: number[]; pipeline_id: number }
    >({
      query: (body) => ({ url: '/reports/bulk/apply-pipeline', method: 'POST', body }),
      invalidatesTags: ['Reports', 'Mirror', 'SyncGroup', 'PipelineConfig'],
    }),
  }),
});

export const {
  useGetDuplicatesReportQuery,
  useGetStorageReportQuery,
  useRefreshStorageReportMutation,
  useGetStatusReportQuery,
  useGetSyncsReportQuery,
  useBulkReassignSyncGroupMutation,
  useBulkChangeTargetGitlabMutation,
  useBulkApplyPipelineMutation,
} = reportsApi;
