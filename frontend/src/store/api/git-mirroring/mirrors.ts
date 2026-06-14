/**
 * @file api/git-mirroring/mirrors.ts
 * @description Mirrors V2 endpoints (CRUD + bulk + sync + freshness + import + integrity)
 * @dependencies api/base.ts
 */

import type {
  Mirror,
  MirrorDetail,
  MirrorCreate,
  MirrorBulkCreate,
  MirrorUpdate,
  ImportMirrorRequest,
  MirrorLog,
  MirrorDuplicateCheck,
  MirrorFilters,
  IntegrityCheckResult,
} from '../../../types';
import { api } from '../base';

export const mirrorsV2Api = api.injectEndpoints({
  endpoints: (builder) => ({
    getMirrors: builder.query<Mirror[], MirrorFilters>({
      query: (params) => ({ url: '/mirroring/mirrors', params }),
      providesTags: ['Mirror'],
    }),
    getMirrorDetail: builder.query<MirrorDetail, number>({
      query: (id) => `/mirroring/mirrors/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Mirror', id }],
    }),
    createMirrorV2: builder.mutation<Mirror, MirrorCreate>({
      query: (body) => ({ url: '/mirroring/mirrors', method: 'POST', body }),
      invalidatesTags: ['Mirror', 'SourceRepository'],
    }),
    bulkCreateMirrors: builder.mutation<Mirror[], MirrorBulkCreate>({
      query: (body) => ({ url: '/mirroring/mirrors/bulk', method: 'POST', body }),
      invalidatesTags: ['Mirror', 'SourceRepository'],
    }),
    updateMirrorV2: builder.mutation<Mirror, { id: number; data: MirrorUpdate }>({
      query: ({ id, data }) => ({ url: `/mirroring/mirrors/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Mirror', id }],
    }),
    deleteMirrorV2: builder.mutation<void, number>({
      query: (id) => ({ url: `/mirroring/mirrors/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Mirror'],
    }),
    triggerMirrorSync: builder.mutation<MirrorLog, number>({
      query: (id) => ({ url: `/mirroring/mirrors/${id}/sync`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Mirror', id }, 'MirrorLog'],
    }),
    triggerFreshnessCheck: builder.mutation<MirrorLog, number>({
      query: (id) => ({ url: `/mirroring/mirrors/${id}/freshness`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Mirror', id }, 'MirrorLog'],
    }),
    importExistingMirror: builder.mutation<Mirror, ImportMirrorRequest>({
      query: (body) => ({ url: '/mirroring/mirrors/import', method: 'POST', body }),
      invalidatesTags: ['Mirror', 'SourceRepository'],
    }),
    checkDuplicates: builder.mutation<
      MirrorDuplicateCheck,
      { source_repo_ids: number[]; sync_group_id: number }
    >({
      query: (body) => ({ url: '/mirroring/mirrors/check-duplicates', method: 'POST', body }),
    }),
    getMirrorLogsV2: builder.query<
      MirrorLog[],
      { mirror_id: number; log_type?: string; limit?: number; offset?: number }
    >({
      query: ({ mirror_id, ...params }) => ({
        url: `/mirroring/mirrors/${mirror_id}/logs`,
        params,
      }),
      providesTags: ['MirrorLog'],
    }),
    checkMirrorIntegrity: builder.mutation<IntegrityCheckResult, number>({
      query: (id) => ({ url: `/mirroring/mirrors/${id}/integrity-check`, method: 'POST' }),
    }),
  }),
});

export const {
  useGetMirrorsQuery,
  useGetMirrorDetailQuery,
  useCreateMirrorV2Mutation,
  useBulkCreateMirrorsMutation,
  useUpdateMirrorV2Mutation,
  useDeleteMirrorV2Mutation,
  useTriggerMirrorSyncMutation,
  useTriggerFreshnessCheckMutation,
  useImportExistingMirrorMutation,
  useCheckDuplicatesMutation,
  useGetMirrorLogsV2Query,
  useCheckMirrorIntegrityMutation,
} = mirrorsV2Api;
