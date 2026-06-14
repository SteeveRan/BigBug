/**
 * @file api/git-mirroring/sync-groups.ts
 * @description Sync Groups CRUD + assign mirrors + apply pipeline
 * @dependencies api/base.ts
 */

import type { SyncGroup, SyncGroupCreate, SyncGroupUpdate } from '../../../types';
import { api } from '../base';

export const syncGroupsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getSyncGroups: builder.query<SyncGroup[], void>({
      query: () => '/mirroring/sync-groups',
      providesTags: ['SyncGroup'],
    }),
    createSyncGroup: builder.mutation<SyncGroup, SyncGroupCreate>({
      query: (body) => ({ url: '/mirroring/sync-groups', method: 'POST', body }),
      invalidatesTags: ['SyncGroup'],
    }),
    getSyncGroup: builder.query<SyncGroup, number>({
      query: (id) => `/mirroring/sync-groups/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'SyncGroup', id }],
    }),
    updateSyncGroup: builder.mutation<SyncGroup, { id: number; data: SyncGroupUpdate }>({
      query: ({ id, data }) => ({
        url: `/mirroring/sync-groups/${id}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'SyncGroup', id }, 'SyncGroup'],
    }),
    deleteSyncGroup: builder.mutation<void, number>({
      query: (id) => ({ url: `/mirroring/sync-groups/${id}`, method: 'DELETE' }),
      invalidatesTags: ['SyncGroup'],
    }),
    assignMirrorsToGroup: builder.mutation<SyncGroup, { group_id: number; mirror_ids: number[] }>({
      query: ({ group_id, ...body }) => ({
        url: `/mirroring/sync-groups/${group_id}/mirrors/bulk`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['SyncGroup', 'Mirror'],
    }),
    applyPipelineToGroup: builder.mutation<SyncGroup, { id: number; pipeline_id: number }>({
      query: ({ id, pipeline_id }) => ({
        url: `/mirroring/sync-groups/${id}/apply-pipeline`,
        method: 'POST',
        body: { pipeline_id },
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'SyncGroup', id }, 'SyncGroup'],
    }),
  }),
});

export const {
  useGetSyncGroupsQuery,
  useCreateSyncGroupMutation,
  useGetSyncGroupQuery,
  useUpdateSyncGroupMutation,
  useDeleteSyncGroupMutation,
  useAssignMirrorsToGroupMutation,
  useApplyPipelineToGroupMutation,
} = syncGroupsApi;
