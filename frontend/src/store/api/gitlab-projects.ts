/**
 * @file api/gitlab-projects.ts
 * @description GitLab Projects CRUD + files/tags/sync/import/share endpoints
 * @dependencies api/base.ts
 */

import type {
  GitlabProject,
  GitlabProjectCreate,
  GitlabProjectFile,
  GitlabProjectFileIn,
  GitlabProjectImport,
  GitlabProjectSyncResult,
  GitlabProjectTag,
  GitlabProjectTagIn,
  GitlabProjectUpdate,
  GitlabProjectsFilters,
} from '../../types';
import { api } from './base';

export interface GitlabProjectListParams extends GitlabProjectsFilters {
  provider_id?: number;
}

export const gitlabProjectsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getGitlabProjects: builder.query<GitlabProject[], GitlabProjectListParams | void>({
      query: (f) => ({ url: '/gitlab-projects', params: f ?? undefined }),
      providesTags: ['GitlabProject'],
    }),
    getGitlabProject: builder.query<GitlabProject, number>({
      query: (id) => `/gitlab-projects/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'GitlabProject', id }],
    }),
    createGitlabProject: builder.mutation<GitlabProject, GitlabProjectCreate>({
      query: (data) => ({ url: '/gitlab-projects', method: 'POST', body: data }),
      invalidatesTags: ['GitlabProject'],
    }),
    updateGitlabProject: builder.mutation<GitlabProject, { id: number; data: GitlabProjectUpdate }>(
      {
        query: ({ id, data }) => ({ url: `/gitlab-projects/${id}`, method: 'PATCH', body: data }),
        invalidatesTags: (_result, _error, { id }) => [
          { type: 'GitlabProject', id },
          'GitlabProject',
        ],
      }
    ),
    deleteGitlabProject: builder.mutation<void, { id: number; hard?: boolean }>({
      query: ({ id, hard }) => ({
        url: `/gitlab-projects/${id}`,
        method: 'DELETE',
        params: { hard: hard ?? false },
      }),
      invalidatesTags: ['GitlabProject'],
    }),
    importGitlabProject: builder.mutation<GitlabProject, GitlabProjectImport>({
      query: (data) => ({ url: '/gitlab-projects/import', method: 'POST', body: data }),
      invalidatesTags: ['GitlabProject'],
    }),
    syncGitlabProject: builder.mutation<GitlabProjectSyncResult, number>({
      query: (id) => ({ url: `/gitlab-projects/${id}/sync`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'GitlabProject', id }],
    }),
    getProjectFiles: builder.query<
      GitlabProjectFile[],
      { id: number; ref?: string; path?: string }
    >({
      query: ({ id, ref, path }) => ({
        url: `/gitlab-projects/${id}/files`,
        params: { ref: ref ?? 'main', path },
      }),
      providesTags: (_result, _error, { id }) => [{ type: 'GitlabProject', id }],
    }),
    pushProjectFile: builder.mutation<GitlabProjectFile, { id: number; data: GitlabProjectFileIn }>(
      {
        query: ({ id, data }) => ({
          url: `/gitlab-projects/${id}/files`,
          method: 'POST',
          body: data,
        }),
        invalidatesTags: (_result, _error, { id }) => [{ type: 'GitlabProject', id }],
      }
    ),
    deleteProjectFile: builder.mutation<
      void,
      { id: number; file_path: string; branch?: string; commit_message?: string }
    >({
      query: ({ id, file_path, branch, commit_message }) => ({
        url: `/gitlab-projects/${id}/files`,
        method: 'DELETE',
        params: { file_path, branch, commit_message },
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'GitlabProject', id }],
    }),
    getProjectTags: builder.query<GitlabProjectTag[], number>({
      query: (id) => `/gitlab-projects/${id}/tags`,
      providesTags: (_result, _error, id) => [{ type: 'GitlabProject', id }],
    }),
    createProjectTag: builder.mutation<GitlabProjectTag, { id: number; data: GitlabProjectTagIn }>({
      query: ({ id, data }) => ({ url: `/gitlab-projects/${id}/tags`, method: 'POST', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'GitlabProject', id }],
    }),
    shareGitlabProject: builder.mutation<GitlabProject, { id: number; team_id: number }>({
      query: ({ id, team_id }) => ({
        url: `/gitlab-projects/${id}/share`,
        method: 'POST',
        body: { team_id },
      }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: 'GitlabProject', id },
        'GitlabProject',
      ],
    }),
    unshareGitlabProject: builder.mutation<GitlabProject, number>({
      query: (id) => ({ url: `/gitlab-projects/${id}/unshare`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'GitlabProject', id }, 'GitlabProject'],
    }),
  }),
});

export const {
  useGetGitlabProjectsQuery,
  useGetGitlabProjectQuery,
  useCreateGitlabProjectMutation,
  useUpdateGitlabProjectMutation,
  useDeleteGitlabProjectMutation,
  useImportGitlabProjectMutation,
  useSyncGitlabProjectMutation,
  useGetProjectFilesQuery,
  usePushProjectFileMutation,
  useDeleteProjectFileMutation,
  useGetProjectTagsQuery,
  useCreateProjectTagMutation,
  useShareGitlabProjectMutation,
  useUnshareGitlabProjectMutation,
} = gitlabProjectsApi;
