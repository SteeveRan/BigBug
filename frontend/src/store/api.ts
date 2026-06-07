import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { RootState } from './index';
import type {
  Permission,
  Role,
  UserPermissions,
  RoleCreate,
  RoleUpdate,
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
  OIDCConfig,
  OIDCConfigUpdate,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: `${BASE_URL}/api`,
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.accessToken;
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: [
    'Project',
    'Mirror',
    'GoldImage',
    'AppImage',
    'User',
    'SyncLog',
    'BuildLog',
    'HelmChart',
    'DockerImage',
    'Permissions',
    'Roles',
    'Integration',
    'OIDCConfig',
  ],
  endpoints: (builder) => ({
    // Auth
    login: builder.mutation<
      { access_token: string; refresh_token: string; token_type: string },
      { username: string; password: string }
    >({
      query: (credentials) => ({
        url: '/auth/login',
        method: 'POST',
        body: credentials,
      }),
    }),
    getMe: builder.query<
      { id: number; username: string; email: string; roles: string[]; is_active: boolean },
      void
    >({
      query: () => '/auth/me',
    }),
    getUserPermissions: builder.query<UserPermissions, void>({
      query: () => '/auth/me/permissions',
      providesTags: ['Permissions'],
    }),
    getSsoConfig: builder.query<
      { enabled: boolean; url: string; realm: string; client_id: string },
      void
    >({
      query: () => '/auth/sso/config',
    }),
    ssoExchange: builder.mutation<
      { access_token: string; refresh_token: string; token_type: string },
      { code: string; redirect_uri: string; code_verifier: string }
    >({
      query: (body) => ({
        url: '/auth/oidc/exchange',
        method: 'POST',
        body,
      }),
    }),

    // Projects
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

    // Mirrors
    listMirrors: builder.query<unknown[], void>({
      query: () => '/mirrors',
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

    // Gold Images
    listGoldImages: builder.query<unknown[], void>({
      query: () => '/gold-images',
      providesTags: ['GoldImage'],
    }),
    getGoldImage: builder.query<unknown, number>({
      query: (id) => `/gold-images/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'GoldImage', id }],
    }),
    createGoldImage: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/gold-images', method: 'POST', body }),
      invalidatesTags: ['GoldImage'],
    }),
    updateGoldImage: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/gold-images/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'GoldImage', id }],
    }),
    deleteGoldImage: builder.mutation<void, number>({
      query: (id) => ({ url: `/gold-images/${id}`, method: 'DELETE' }),
      invalidatesTags: ['GoldImage'],
    }),
    triggerGoldBuild: builder.mutation<unknown, { id: number; version_tag: string; arch: string }>({
      query: ({ id, ...body }) => ({ url: `/gold-images/${id}/build`, method: 'POST', body }),
      invalidatesTags: ['BuildLog'],
    }),

    // App Images
    listAppImages: builder.query<unknown[], void>({
      query: () => '/app-images',
      providesTags: ['AppImage'],
    }),
    getAppImage: builder.query<unknown, number>({
      query: (id) => `/app-images/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'AppImage', id }],
    }),
    createAppImage: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/app-images', method: 'POST', body }),
      invalidatesTags: ['AppImage'],
    }),
    updateAppImage: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/app-images/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'AppImage', id }],
    }),
    deleteAppImage: builder.mutation<void, number>({
      query: (id) => ({ url: `/app-images/${id}`, method: 'DELETE' }),
      invalidatesTags: ['AppImage'],
    }),
    triggerAppBuild: builder.mutation<unknown, { id: number; version_tag: string; arch: string }>({
      query: ({ id, ...body }) => ({ url: `/app-images/${id}/build`, method: 'POST', body }),
      invalidatesTags: ['BuildLog'],
    }),

    // Helm Charts
    listHelmCharts: builder.query<unknown[], void>({
      query: () => '/helm-charts',
      providesTags: ['HelmChart'],
    }),
    getHelmChart: builder.query<unknown, number>({
      query: (id) => `/helm-charts/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'HelmChart', id }],
    }),
    createHelmChart: builder.mutation<
      unknown,
      { name: string; repo_url: string; description?: string }
    >({
      query: (body) => ({ url: '/helm-charts', method: 'POST', body }),
      invalidatesTags: ['HelmChart'],
    }),
    updateHelmChart: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/helm-charts/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'HelmChart', id }],
    }),
    deleteHelmChart: builder.mutation<void, number>({
      query: (id) => ({ url: `/helm-charts/${id}`, method: 'DELETE' }),
      invalidatesTags: ['HelmChart'],
    }),
    indexHelmChart: builder.mutation<unknown, number>({
      query: (id) => ({ url: `/helm-charts/${id}/index`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'HelmChart', id }],
    }),
    getHelmChartVersions: builder.query<unknown[], number>({
      query: (id) => `/helm-charts/${id}/versions`,
    }),
    getHelmChartLogs: builder.query<unknown[], number>({
      query: (id) => `/helm-charts/${id}/logs`,
    }),

    // Docker Images
    listDockerImages: builder.query<unknown[], void>({
      query: () => '/docker-images',
      providesTags: ['DockerImage'],
    }),
    getDockerImage: builder.query<unknown, number>({
      query: (id) => `/docker-images/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'DockerImage', id }],
    }),
    createDockerImage: builder.mutation<
      unknown,
      { name: string; registry_url: string; description?: string; image_name?: string }
    >({
      query: (body) => ({ url: '/docker-images', method: 'POST', body }),
      invalidatesTags: ['DockerImage'],
    }),
    updateDockerImage: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/docker-images/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'DockerImage', id }],
    }),
    deleteDockerImage: builder.mutation<void, number>({
      query: (id) => ({ url: `/docker-images/${id}`, method: 'DELETE' }),
      invalidatesTags: ['DockerImage'],
    }),
    indexDockerImage: builder.mutation<unknown, { id: number; image_name: string }>({
      query: ({ id, image_name }) => ({
        url: `/docker-images/${id}/index?image_name=${encodeURIComponent(image_name)}`,
        method: 'POST',
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'DockerImage', id }],
    }),
    getDockerImageTags: builder.query<unknown[], number>({
      query: (id) => `/docker-images/${id}/tags`,
    }),
    getDockerImageLogs: builder.query<unknown[], number>({
      query: (id) => `/docker-images/${id}/logs`,
    }),

    // Admin
    listUsers: builder.query<unknown[], void>({
      query: () => '/admin/users',
      providesTags: ['User'],
    }),
    createUser: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/admin/users', method: 'POST', body }),
      invalidatesTags: ['User'],
    }),
    updateUser: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/admin/users/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: ['User'],
    }),
    deleteUser: builder.mutation<void, number>({
      query: (id) => ({ url: `/admin/users/${id}`, method: 'DELETE' }),
      invalidatesTags: ['User'],
    }),
    // RBAC: Permissions
    getAllPermissions: builder.query<Permission[], void>({
      query: () => '/admin/permissions',
      providesTags: ['Permissions'],
    }),

    // RBAC: Roles
    getAllRoles: builder.query<Role[], void>({
      query: () => '/admin/roles',
      providesTags: ['Roles'],
    }),
    getRoleById: builder.query<Role, number>({
      query: (id) => `/admin/roles/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Roles', id }],
    }),
    createRole: builder.mutation<Role, RoleCreate>({
      query: (body) => ({
        url: '/admin/roles',
        method: 'POST',
        body,
      }),
      invalidatesTags: ['Roles'],
    }),
    updateRole: builder.mutation<Role, { id: number; data: RoleUpdate }>({
      query: ({ id, data }) => ({
        url: `/admin/roles/${id}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Roles', id }, 'Roles'],
    }),
    deleteRole: builder.mutation<void, number>({
      query: (id) => ({
        url: `/admin/roles/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Roles'],
    }),

    // ──── GitLab Instances ──────────────────────────────────────────────

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

    // ──── Harbor Instances ──────────────────────────────────────────────

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

    // ──── GitHub Instances ──────────────────────────────────────────────

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

    // ──── Docker Registry Instances ──────────────────────────────────────

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

    // ──── Helm Repository Instances ──────────────────────────────────────

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

    // ──── OIDC Configuration ──────────────────────────────────────────────

    getOidcConfig: builder.query<OIDCConfig, void>({
      query: () => '/auth/admin/oidc-config',
      providesTags: ['OIDCConfig'],
    }),
    updateOidcConfig: builder.mutation<OIDCConfig, OIDCConfigUpdate>({
      query: (data) => ({
        url: '/auth/admin/oidc-config',
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: ['OIDCConfig'],
    }),
  }),
});

export const {
  useLoginMutation,
  useGetMeQuery,
  useGetSsoConfigQuery,
  useSsoExchangeMutation,
  useListProjectsQuery,
  useGetProjectQuery,
  useCreateProjectMutation,
  useImportProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
  useRefreshProjectMutation,
  useListMirrorsQuery,
  useGetMirrorQuery,
  useCreateMirrorMutation,
  useImportMirrorMutation,
  useTriggerSyncMutation,
  useGetMirrorLogsQuery,
  useGetMirrorScheduleQuery,
  useUpdateMirrorScheduleMutation,
  useListGoldImagesQuery,
  useGetGoldImageQuery,
  useCreateGoldImageMutation,
  useUpdateGoldImageMutation,
  useDeleteGoldImageMutation,
  useTriggerGoldBuildMutation,
  useListAppImagesQuery,
  useGetAppImageQuery,
  useCreateAppImageMutation,
  useUpdateAppImageMutation,
  useDeleteAppImageMutation,
  useTriggerAppBuildMutation,
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
  useGetUserPermissionsQuery,
  useGetAllPermissionsQuery,
  useGetAllRolesQuery,
  useGetRoleByIdQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
  useListHelmChartsQuery,
  useGetHelmChartQuery,
  useCreateHelmChartMutation,
  useUpdateHelmChartMutation,
  useDeleteHelmChartMutation,
  useIndexHelmChartMutation,
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
  useListDockerImagesQuery,
  useGetDockerImageQuery,
  useCreateDockerImageMutation,
  useUpdateDockerImageMutation,
  useDeleteDockerImageMutation,
  useIndexDockerImageMutation,
  useGetDockerImageTagsQuery,
  useGetDockerImageLogsQuery,
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
  useGetOidcConfigQuery,
  useUpdateOidcConfigMutation,
} = api;
