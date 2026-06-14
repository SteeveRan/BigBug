/**
 * @file api/projects-legacy.ts
 * @description Projects (legacy) + GithubRelease endpoints
 * @dependencies api/base.ts
 */

import type { GithubRelease } from '../../types';
import { api } from './base';

export const projectsLegacyApi = api.injectEndpoints({
  endpoints: (builder) => ({
    listProjects: builder.query<unknown[], void>({
      query: () => '/projects',
      providesTags: ['Project'],
    }),
    getProject: builder.query<unknown, number>({
      query: (id) => `/projects/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Project', id }],
    }),
    createProject: builder.mutation<unknown, { github_url: string }>({
      query: (body) => ({ url: '/projects', method: 'POST', body }),
      invalidatesTags: ['Project'],
    }),
    importProject: builder.mutation<unknown, { github_url: string; gitlab_url?: string }>({
      query: (body) => ({ url: '/projects/import', method: 'POST', body }),
      invalidatesTags: ['Project'],
    }),
    updateProject: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/projects/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Project', id }],
    }),
    deleteProject: builder.mutation<void, number>({
      query: (id) => ({ url: `/projects/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Project'],
    }),
    refreshProject: builder.mutation<unknown, number>({
      query: (id) => ({ url: `/projects/${id}/refresh`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Project', id }],
    }),
    getProjectReleases: builder.query<GithubRelease[], number>({
      query: (id) => `/projects/${id}/releases`,
      providesTags: (_result, _error, id) => [{ type: 'Project', id }],
    }),
  }),
});

export const {
  useListProjectsQuery,
  useGetProjectQuery,
  useCreateProjectMutation,
  useImportProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
  useRefreshProjectMutation,
  useGetProjectReleasesQuery,
} = projectsLegacyApi;
