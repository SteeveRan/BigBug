/**
 * @file api/mirrors-legacy.ts
 * @description Mirrors v1 (legacy) CRUD + logs/schedule
 * @dependencies api/base.ts
 */

import { api } from './base';

export const mirrorsLegacyApi = api.injectEndpoints({
  endpoints: (builder) => ({
    listMirrors: builder.query<unknown[], void>({
      query: () => '/mirroring/mirrors/',
      providesTags: ['Mirror'],
    }),
    getMirror: builder.query<unknown, number>({
      query: (id) => `/mirrors/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Mirror', id }],
    }),
    createMirror: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/mirrors', method: 'POST', body }),
      invalidatesTags: ['Mirror'],
    }),
    importMirror: builder.mutation<unknown, { github_url: string; gitlab_url: string }>({
      query: (body) => ({ url: '/mirrors/import', method: 'POST', body }),
      invalidatesTags: ['Mirror', 'Project'],
    }),
    triggerSync: builder.mutation<unknown, number>({
      query: (id) => ({ url: `/mirrors/${id}/sync`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Mirror', id }, 'SyncLog'],
    }),
    getMirrorLogs: builder.query<unknown[], number>({
      query: (id) => `/mirrors/${id}/logs`,
      providesTags: ['SyncLog'],
    }),
    getMirrorSchedule: builder.query<unknown, number>({
      query: (id) => `/mirrors/${id}/schedule`,
    }),
    updateMirrorSchedule: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/mirrors/${id}/schedule`, method: 'PATCH', body: data }),
    }),
  }),
});

export const {
  useListMirrorsQuery,
  useGetMirrorQuery,
  useCreateMirrorMutation,
  useImportMirrorMutation,
  useTriggerSyncMutation,
  useGetMirrorLogsQuery,
  useGetMirrorScheduleQuery,
  useUpdateMirrorScheduleMutation,
} = mirrorsLegacyApi;
