/**
 * @file api/git-mirroring/repositories.ts
 * @description Source Repositories endpoints (list/detail/create + releases + readme)
 * @dependencies api/base.ts
 */

import type {
  SourceRepository,
  SourceRepositoryCreate,
  SourceRepositoryRelease,
  SourceRepositoryReadme,
} from '../../../types';
import { api } from '../base';

export const sourceRepositoriesApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getSourceRepositories: builder.query<
      SourceRepository[],
      {
        group_id: number;
        discovery_status?: number;
        is_archived?: boolean;
        search?: string;
        limit?: number;
        offset?: number;
      }
    >({
      query: ({ group_id, ...params }) => ({
        url: `/mirroring/groups/${group_id}/repositories`,
        params,
      }),
      providesTags: ['SourceRepository'],
    }),
    getSourceRepository: builder.query<SourceRepository, number>({
      query: (id) => `/mirroring/repositories/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'SourceRepository', id }],
    }),
    getRepositoryReleases: builder.query<
      SourceRepositoryRelease[],
      { repository_id: number; include_prereleases?: boolean }
    >({
      query: ({ repository_id }) => `/mirroring/repositories/${repository_id}/releases`,
      providesTags: (_result, _error, { repository_id }) => [
        { type: 'SourceRepository', id: repository_id },
      ],
    }),
    getRepositoryReadme: builder.query<SourceRepositoryReadme, number>({
      query: (id) => `/mirroring/repositories/${id}/readme`,
    }),
    createSourceRepository: builder.mutation<
      SourceRepository,
      SourceRepositoryCreate
    >({
      query: (data) => ({
        url: '/mirroring/repositories/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['SourceRepository'],
    }),
    deleteSourceRepository: builder.mutation<void, number>({
      query: (id) => ({ url: `/mirroring/repositories/${id}`, method: 'DELETE' }),
      invalidatesTags: ['SourceRepository'],
    }),
    refreshSourceRepository: builder.mutation<SourceRepository, number>({
      query: (id) => ({
        url: `/mirroring/repositories/${id}/refresh`,
        method: 'POST',
      }),
      invalidatesTags: (_result, _error, id) => [
        { type: 'SourceRepository', id },
      ],
    }),
  }),
});

export const {
  useGetSourceRepositoriesQuery,
  useGetSourceRepositoryQuery,
  useGetRepositoryReleasesQuery,
  useGetRepositoryReadmeQuery,
  useCreateSourceRepositoryMutation,
  useDeleteSourceRepositoryMutation,
  useRefreshSourceRepositoryMutation,
} = sourceRepositoriesApi;
