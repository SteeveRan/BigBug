/**
 * @file api/git-mirroring/orphaned.ts
 * @description Orphaned Mirrors endpoints (list + reassign + move-target + delete)
 * @dependencies api/base.ts
 */

import type { OrphanedMirrorListResponse, IntegrityCheckResult } from '../../../types';
import { api } from '../base';

export const orphanedApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getOrphanedMirrors: builder.query<
      OrphanedMirrorListResponse,
      { page?: number; page_size?: number; search?: string; gitlab_instance_id?: number }
    >({
      query: (params) => ({ url: '/mirroring/orphaned-mirrors', params }),
      providesTags: ['OrphanedMirrors'],
    }),
    reassignOrphanedMirror: builder.mutation<
      void,
      { mirrorId: number; syncGroupId: number }
    >({
      query: ({ mirrorId, syncGroupId }) => ({
        url: `/mirroring/orphaned/${mirrorId}/reassign`,
        method: 'POST',
        body: { sync_group_id: syncGroupId },
      }),
      invalidatesTags: ['OrphanedMirrors', 'Mirror'],
    }),
    moveOrphanedTarget: builder.mutation<
      void,
      { mirrorId: number; targetPath: string }
    >({
      query: ({ mirrorId, targetPath }) => ({
        url: `/mirroring/orphaned/${mirrorId}/move-target`,
        method: 'POST',
        body: { target_path: targetPath },
      }),
      invalidatesTags: ['OrphanedMirrors', 'Mirror'],
    }),
    deleteOrphanedMirror: builder.mutation<void, number>({
      query: (id) => ({ url: `/mirroring/orphaned/${id}`, method: 'DELETE' }),
      invalidatesTags: ['OrphanedMirrors'],
    }),
  }),
});

export const {
  useGetOrphanedMirrorsQuery,
  useReassignOrphanedMirrorMutation,
  useMoveOrphanedTargetMutation,
  useDeleteOrphanedMirrorMutation,
} = orphanedApi;
