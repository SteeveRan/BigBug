/**
 * @file api/integrations.ts
 * @description Integration instances: GitLab, Harbor, GitHub, Docker Registry, Helm Repository
 * @dependencies api/base.ts
 */

import type {
  GitlabInstance,
  GitlabInstanceCreate,
  GitlabInstanceUpdate,
  HarborInstance,
  HarborInstanceCreate,
  HarborInstanceUpdate,
  GithubInstance,
  GithubInstanceCreate,
  GithubInstanceUpdate,
  DockerRegistryInstance,
  DockerRegistryInstanceCreate,
  DockerRegistryInstanceUpdate,
  HelmRepositoryInstance,
  HelmRepositoryInstanceCreate,
  HelmRepositoryInstanceUpdate,
  ConnectionTestResult,
} from '../../types';
import { api } from './base';

export const integrationsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    // ── GitLab ───────────────────────────────────────────────────

    getGitlabInstances: builder.query<GitlabInstance[], void>({
      query: () => '/integrations/gitlab',
      providesTags: ['Integration'],
    }),
    getGitlabInstance: builder.query<GitlabInstance, number>({
      query: (id) => `/integrations/gitlab/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Integration', id }],
    }),
    createGitlabInstance: builder.mutation<GitlabInstance, GitlabInstanceCreate>({
      query: (body) => ({ url: '/integrations/gitlab', method: 'POST', body }),
      invalidatesTags: ['Integration'],
    }),
    updateGitlabInstance: builder.mutation<
      GitlabInstance,
      { id: number; data: GitlabInstanceUpdate }
    >({
      query: ({ id, data }) => ({ url: `/integrations/gitlab/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Integration', id }, 'Integration'],
    }),
    deleteGitlabInstance: builder.mutation<void, number>({
      query: (id) => ({ url: `/integrations/gitlab/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Integration'],
    }),
    testGitlabConnection: builder.mutation<ConnectionTestResult, number>({
      query: (id) => ({ url: `/integrations/gitlab/${id}/test`, method: 'POST' }),
      invalidatesTags: ['Integration'],
    }),

    // ── Harbor ───────────────────────────────────────────────────

    getHarborInstances: builder.query<HarborInstance[], void>({
      query: () => '/integrations/harbor',
      providesTags: ['Integration'],
    }),
    getHarborInstance: builder.query<HarborInstance, number>({
      query: (id) => `/integrations/harbor/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Integration', id }],
    }),
    createHarborInstance: builder.mutation<HarborInstance, HarborInstanceCreate>({
      query: (body) => ({ url: '/integrations/harbor', method: 'POST', body }),
      invalidatesTags: ['Integration'],
    }),
    updateHarborInstance: builder.mutation<
      HarborInstance,
      { id: number; data: HarborInstanceUpdate }
    >({
      query: ({ id, data }) => ({ url: `/integrations/harbor/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Integration', id }, 'Integration'],
    }),
    deleteHarborInstance: builder.mutation<void, number>({
      query: (id) => ({ url: `/integrations/harbor/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Integration'],
    }),
    testHarborConnection: builder.mutation<ConnectionTestResult, number>({
      query: (id) => ({ url: `/integrations/harbor/${id}/test`, method: 'POST' }),
      invalidatesTags: ['Integration'],
    }),

    // ── GitHub ───────────────────────────────────────────────────

    getGithubInstances: builder.query<GithubInstance[], void>({
      query: () => '/integrations/github',
      providesTags: ['Integration'],
    }),
    getGithubInstance: builder.query<GithubInstance, number>({
      query: (id) => `/integrations/github/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Integration', id }],
    }),
    createGithubInstance: builder.mutation<GithubInstance, GithubInstanceCreate>({
      query: (body) => ({ url: '/integrations/github', method: 'POST', body }),
      invalidatesTags: ['Integration'],
    }),
    updateGithubInstance: builder.mutation<
      GithubInstance,
      { id: number; data: GithubInstanceUpdate }
    >({
      query: ({ id, data }) => ({ url: `/integrations/github/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Integration', id }, 'Integration'],
    }),
    deleteGithubInstance: builder.mutation<void, number>({
      query: (id) => ({ url: `/integrations/github/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Integration'],
    }),
    testGithubConnection: builder.mutation<ConnectionTestResult, number>({
      query: (id) => ({ url: `/integrations/github/${id}/test`, method: 'POST' }),
      invalidatesTags: ['Integration'],
    }),

    // ── Docker Registry ──────────────────────────────────────────

    getDockerRegistryInstances: builder.query<DockerRegistryInstance[], void>({
      query: () => '/integrations/docker-registry',
      providesTags: ['Integration'],
    }),
    getDockerRegistryInstance: builder.query<DockerRegistryInstance, number>({
      query: (id) => `/integrations/docker-registry/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Integration', id }],
    }),
    createDockerRegistryInstance: builder.mutation<
      DockerRegistryInstance,
      DockerRegistryInstanceCreate
    >({
      query: (body) => ({ url: '/integrations/docker-registry', method: 'POST', body }),
      invalidatesTags: ['Integration'],
    }),
    updateDockerRegistryInstance: builder.mutation<
      DockerRegistryInstance,
      { id: number; data: DockerRegistryInstanceUpdate }
    >({
      query: ({ id, data }) => ({
        url: `/integrations/docker-registry/${id}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Integration', id }, 'Integration'],
    }),
    deleteDockerRegistryInstance: builder.mutation<void, number>({
      query: (id) => ({ url: `/integrations/docker-registry/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Integration'],
    }),
    testDockerRegistryConnection: builder.mutation<ConnectionTestResult, number>({
      query: (id) => ({ url: `/integrations/docker-registry/${id}/test`, method: 'POST' }),
      invalidatesTags: ['Integration'],
    }),

    // ── Helm Repository ──────────────────────────────────────────

    getHelmRepositoryInstances: builder.query<HelmRepositoryInstance[], void>({
      query: () => '/integrations/helm-repository',
      providesTags: ['Integration'],
    }),
    getHelmRepositoryInstance: builder.query<HelmRepositoryInstance, number>({
      query: (id) => `/integrations/helm-repository/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Integration', id }],
    }),
    createHelmRepositoryInstance: builder.mutation<
      HelmRepositoryInstance,
      HelmRepositoryInstanceCreate
    >({
      query: (body) => ({ url: '/integrations/helm-repository', method: 'POST', body }),
      invalidatesTags: ['Integration'],
    }),
    updateHelmRepositoryInstance: builder.mutation<
      HelmRepositoryInstance,
      { id: number; data: HelmRepositoryInstanceUpdate }
    >({
      query: ({ id, data }) => ({
        url: `/integrations/helm-repository/${id}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Integration', id }, 'Integration'],
    }),
    deleteHelmRepositoryInstance: builder.mutation<void, number>({
      query: (id) => ({ url: `/integrations/helm-repository/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Integration'],
    }),
    testHelmRepositoryConnection: builder.mutation<ConnectionTestResult, number>({
      query: (id) => ({ url: `/integrations/helm-repository/${id}/test`, method: 'POST' }),
      invalidatesTags: ['Integration'],
    }),
  }),
});

export const {
  useGetGitlabInstancesQuery,
  useGetGitlabInstanceQuery,
  useCreateGitlabInstanceMutation,
  useUpdateGitlabInstanceMutation,
  useDeleteGitlabInstanceMutation,
  useTestGitlabConnectionMutation,
  useGetHarborInstancesQuery,
  useGetHarborInstanceQuery,
  useCreateHarborInstanceMutation,
  useUpdateHarborInstanceMutation,
  useDeleteHarborInstanceMutation,
  useTestHarborConnectionMutation,
  useGetGithubInstancesQuery,
  useGetGithubInstanceQuery,
  useCreateGithubInstanceMutation,
  useUpdateGithubInstanceMutation,
  useDeleteGithubInstanceMutation,
  useTestGithubConnectionMutation,
  useGetDockerRegistryInstancesQuery,
  useGetDockerRegistryInstanceQuery,
  useCreateDockerRegistryInstanceMutation,
  useUpdateDockerRegistryInstanceMutation,
  useDeleteDockerRegistryInstanceMutation,
  useTestDockerRegistryConnectionMutation,
  useGetHelmRepositoryInstancesQuery,
  useGetHelmRepositoryInstanceQuery,
  useCreateHelmRepositoryInstanceMutation,
  useUpdateHelmRepositoryInstanceMutation,
  useDeleteHelmRepositoryInstanceMutation,
  useTestHelmRepositoryConnectionMutation,
} = integrationsApi;
