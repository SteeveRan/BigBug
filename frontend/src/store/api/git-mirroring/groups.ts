/**
 * @file api/git-mirroring/groups.ts
 * @description Source Groups CRUD + import + refresh
 * @dependencies api/base.ts
 */

import type { SourceGroup } from '../../../types';
import { api } from '../base';

export const sourceGroupsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getSourceGroups: builder.query<SourceGroup[], number | undefined>({
      query: (providerId) =>
        `/mirroring/groups${providerId ? `?source_provider_id=${providerId}` : ''}`,
      providesTags: ['SourceGroup'],
    }),
    importSourceGroup: builder.mutation<
      SourceGroup,
      { providerId?: number; groupName: string }
    >({
      query: ({ providerId, groupName }) => ({
        url: `/mirroring/groups/import?group_name=${encodeURIComponent(groupName)}${providerId ? `&source_provider_id=${providerId}` : ''}`,
        method: 'POST',
      }),
      invalidatesTags: ['SourceGroup'],
    }),
    getSourceGroup: builder.query<SourceGroup, number>({
      query: (id) => `/mirroring/groups/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'SourceGroup', id }],
    }),
    refreshSourceGroup: builder.mutation<SourceGroup, number>({
      query: (id) => ({ url: `/mirroring/groups/${id}/refresh`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'SourceGroup', id }],
    }),
    deleteSourceGroup: builder.mutation<void, number>({
      query: (id) => ({ url: `/mirroring/groups/${id}`, method: 'DELETE' }),
      invalidatesTags: ['SourceGroup'],
    }),
  }),
});

export const {
  useGetSourceGroupsQuery,
  useImportSourceGroupMutation,
  useGetSourceGroupQuery,
  useRefreshSourceGroupMutation,
  useDeleteSourceGroupMutation,
} = sourceGroupsApi;
