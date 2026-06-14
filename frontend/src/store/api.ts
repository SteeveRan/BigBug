import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { RootState } from './index';
import type {
  Permission,
  Role,
  RoleScope,
  RoleScopeUpdate,
  ScopeItemRequest,
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
  PipelineRun,
  PipelineRunCreate,
  PipelineRunList,
  GitLabComponent,
  GitLabComponentCreate,
  GitLabComponentUpdate,
  AuditLogList,
  VulnerabilityScanResult,
  ScanRequest,
  SignImageRequest,
  SignImageResult,
  VerifyImageRequest,
  VerifyImageResult,
  DockerImageSource,
  DockerImageSourceDetail,
  DockerImageTag,
  DockerSyncLog,
  DockerSyncSchedule,
  DockerImageCompareResponse,
  AnalyzeImageResponse,
  GithubRelease,
  // Git Mirroring V2
  SourceProvider,
  SourceProviderCreate,
  SourceProviderUpdate,
  SourceGroup,
  SourceRepository,
  SourceRepositoryReadme,
  SourceRepositoryRelease,
  Mirror,
  MirrorDetail,
  MirrorCreate,
  MirrorBulkCreate,
  MirrorUpdate,
  ImportMirrorRequest,
  MirrorLog,
  MirrorDuplicateCheck,
  MirrorFilters,
  SyncGroup,
  SyncGroupCreate,
  SyncGroupUpdate,
  PipelineConfig,
  PipelineConfigCreate,
  PipelineConfigUpdate,
  // Orphaned Mirrors
  OrphanedMirrorListResponse,
  IntegrityCheckResult,
  // Reports
  DuplicatesReport,
  StorageReport,
  StorageRefreshStatus,
  StatusReport,
  SyncsReport,
  BulkOperationResponse,
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
    'DockerSyncSchedule',
    'Permissions',
    'Roles',
    'RoleScope',
    'Integration',
    'OIDCConfig',
    'Pipeline',
    'Component',
    'AuditLog',
    'SourceProvider',
    'SourceGroup',
    'SourceRepository',
    'MirrorLog',
    'SyncGroup',
    'PipelineConfig',
    'OrphanedMirrors',
    'Reports',
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
    getProjectReleases: builder.query<GithubRelease[], number>({
      query: (id) => `/projects/${id}/releases`,
      providesTags: (_result, _error, id) => [{ type: 'Project', id }],
    }),

    // Mirrors
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
    scanGoldImageVersion: builder.mutation<
      VulnerabilityScanResult,
      { imageId: number; versionId: number } & ScanRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/gold-images/${imageId}/versions/${versionId}/scan`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['GoldImage'],
    }),
    getGoldImageScanResults: builder.mutation<
      VulnerabilityScanResult,
      { imageId: number; versionId: number } & ScanRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/gold-images/${imageId}/versions/${versionId}/scan/results`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['GoldImage'],
    }),
    signGoldImageVersion: builder.mutation<
      SignImageResult,
      { imageId: number; versionId: number } & SignImageRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/gold-images/${imageId}/versions/${versionId}/sign`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['GoldImage'],
    }),
    verifyGoldImageVersion: builder.mutation<
      VerifyImageResult,
      { imageId: number; versionId: number } & VerifyImageRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/gold-images/${imageId}/versions/${versionId}/verify`,
        method: 'POST',
        body,
      }),
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
    scanAppImageVersion: builder.mutation<
      VulnerabilityScanResult,
      { imageId: number; versionId: number } & ScanRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/app-images/${imageId}/versions/${versionId}/scan`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['AppImage'],
    }),
    signAppImageVersion: builder.mutation<
      SignImageResult,
      { imageId: number; versionId: number } & SignImageRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/app-images/${imageId}/versions/${versionId}/sign`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['AppImage'],
    }),
    verifyAppImageVersion: builder.mutation<
      VerifyImageResult,
      { imageId: number; versionId: number } & VerifyImageRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/app-images/${imageId}/versions/${versionId}/verify`,
        method: 'POST',
        body,
      }),
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
    listDockerImages: builder.query<DockerImageSource[], void>({
      query: () => '/docker-images',
      providesTags: ['DockerImage'],
    }),
    getDockerImage: builder.query<DockerImageSourceDetail, number>({
      query: (id) => `/docker-images/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'DockerImage', id }],
    }),
    createDockerImage: builder.mutation<
      DockerImageSource,
      {
        name: string;
        registry_url: string;
        description?: string;
        image_name?: string;
        registry_instance_id?: number;
        target_registry_url?: string;
        target_project?: string;
      }
    >({
      query: (body) => ({ url: '/docker-images', method: 'POST', body }),
      invalidatesTags: ['DockerImage'],
    }),
    updateDockerImage: builder.mutation<
      DockerImageSource,
      { id: number; data: Partial<DockerImageSource> }
    >({
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
    getDockerImageTags: builder.query<DockerImageTag[], number>({
      query: (id) => `/docker-images/${id}/tags`,
    }),
    getDockerImageLogs: builder.query<DockerSyncLog[], number>({
      query: (id) => `/docker-images/${id}/logs`,
    }),
    batchDeleteDockerTags: builder.mutation<void, { sourceId: number; tagIds: number[] }>({
      query: ({ sourceId, tagIds }) => ({
        url: `/docker-images/${sourceId}/tags/batch`,
        method: 'DELETE',
        body: { tag_ids: tagIds },
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [{ type: 'DockerImage', id: sourceId }],
    }),

    analyzeDockerImage: builder.mutation<AnalyzeImageResponse, { image_name: string }>({
      query: (body) => ({ url: '/docker-images/analyze', method: 'POST', body }),
    }),

    compareDockerImages: builder.query<
      DockerImageCompareResponse,
      { sourceAId: number; sourceBId: number }
    >({
      query: ({ sourceAId, sourceBId }) => `/docker-images/${sourceAId}/compare/${sourceBId}`,
    }),

    // Sync Schedule
    getDockerSyncSchedules: builder.query<DockerSyncSchedule[], number>({
      query: (sourceId) => `/docker-images/${sourceId}/schedule`,
      providesTags: (_result, _error, sourceId) => [{ type: 'DockerSyncSchedule', id: sourceId }],
    }),

    createDockerSyncSchedule: builder.mutation<
      DockerSyncSchedule,
      {
        sourceId: number;
        data: { cron_expression?: string; is_enabled?: boolean; use_default_schedule?: boolean };
      }
    >({
      query: ({ sourceId, data }) => ({
        url: `/docker-images/${sourceId}/schedule`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'DockerSyncSchedule', id: sourceId },
      ],
    }),

    updateDockerSyncSchedule: builder.mutation<
      DockerSyncSchedule,
      {
        sourceId: number;
        scheduleId: number;
        data: { cron_expression?: string; is_enabled?: boolean; use_default_schedule?: boolean };
      }
    >({
      query: ({ sourceId, scheduleId, data }) => ({
        url: `/docker-images/${sourceId}/schedule/${scheduleId}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'DockerSyncSchedule', id: sourceId },
      ],
    }),

    deleteDockerSyncSchedule: builder.mutation<void, { sourceId: number; scheduleId: number }>({
      query: ({ sourceId, scheduleId }) => ({
        url: `/docker-images/${sourceId}/schedule/${scheduleId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'DockerSyncSchedule', id: sourceId },
      ],
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

    // RBAC: Role Scope
    getRoleScope: builder.query<
      RoleScope,
      { roleId: number; scopeType: 'source-groups' | 'credentials' | 'sync-groups' }
    >({
      query: ({ roleId, scopeType }) => `/admin/roles/${roleId}/scopes/${scopeType}`,
      providesTags: (_result, _error, { roleId }) => [{ type: 'RoleScope', id: roleId }],
    }),
    addRoleScopeItem: builder.mutation<
      RoleScope,
      {
        roleId: number;
        scopeType: 'source-groups' | 'credentials' | 'sync-groups';
        item: ScopeItemRequest;
      }
    >({
      query: ({ roleId, scopeType, item }) => ({
        url: `/admin/roles/${roleId}/scopes/${scopeType}`,
        method: 'POST',
        body: item,
      }),
      invalidatesTags: (_result, _error, { roleId }) => [{ type: 'RoleScope', id: roleId }],
    }),
    setRoleScope: builder.mutation<
      RoleScope,
      {
        roleId: number;
        scopeType: 'source-groups' | 'credentials' | 'sync-groups';
        data: RoleScopeUpdate;
      }
    >({
      query: ({ roleId, scopeType, data }) => ({
        url: `/admin/roles/${roleId}/scopes/${scopeType}`,
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: (_result, _error, { roleId }) => [{ type: 'RoleScope', id: roleId }],
    }),
    removeRoleScopeItem: builder.mutation<
      void,
      { roleId: number; scopeType: 'source-groups' | 'credentials' | 'sync-groups'; itemId: number }
    >({
      query: ({ roleId, scopeType, itemId }) => ({
        url: `/admin/roles/${roleId}/scopes/${scopeType}/${itemId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, { roleId }) => [{ type: 'RoleScope', id: roleId }],
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

    // ──── Pipeline Runs ───────────────────────────────────────────────────

    getPipelineRuns: builder.query<PipelineRunList, { page?: number; status?: number }>({
      query: (params) => ({ url: '/pipelines', params }),
      providesTags: ['Pipeline'],
    }),
    getPipelineRun: builder.query<PipelineRun, number>({
      query: (id) => `/pipelines/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Pipeline', id }],
    }),
    triggerPipeline: builder.mutation<PipelineRun, PipelineRunCreate>({
      query: (data) => ({ url: '/pipelines', method: 'POST', body: data }),
      invalidatesTags: ['Pipeline'],
    }),
    cancelPipeline: builder.mutation<PipelineRun, number>({
      query: (id) => ({ url: `/pipelines/${id}/cancel`, method: 'POST' }),
      invalidatesTags: ['Pipeline'],
    }),
    retryPipeline: builder.mutation<PipelineRun, number>({
      query: (id) => ({ url: `/pipelines/${id}/retry`, method: 'POST' }),
      invalidatesTags: ['Pipeline'],
    }),

    // ──── GitLab Components ───────────────────────────────────────────────

    getComponents: builder.query<GitLabComponent[], void>({
      query: () => '/components',
      providesTags: ['Component'],
    }),
    createComponent: builder.mutation<GitLabComponent, GitLabComponentCreate>({
      query: (data) => ({ url: '/components', method: 'POST', body: data }),
      invalidatesTags: ['Component'],
    }),
    updateComponent: builder.mutation<GitLabComponent, { id: number; data: GitLabComponentUpdate }>(
      {
        query: ({ id, data }) => ({ url: `/components/${id}`, method: 'PATCH', body: data }),
        invalidatesTags: (_result, _error, { id }) => [{ type: 'Component', id }, 'Component'],
      }
    ),
    deleteComponent: builder.mutation<void, number>({
      query: (id) => ({ url: `/components/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Component'],
    }),

    // ──── GitLab Component Run ───────────────────────────────────────────────

    runComponent: builder.mutation<
      PipelineRun,
      { componentId: number; data: { ref: string; inputs: Record<string, string> } }
    >({
      query: ({ componentId, data }) => ({
        url: `/components/${componentId}/run`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Component', 'Pipeline'],
    }),

    // ──── Pipeline Configurations (Git Mirroring V2) ──────────────────────

    getPipelineConfigs: builder.query<
      PipelineConfig[],
      { search?: string; is_enabled?: boolean } | void
    >({
      query: (params) => ({ url: '/pipelines/configs', params: params ?? undefined }),
      providesTags: ['PipelineConfig'],
    }),
    getPipelineConfig: builder.query<PipelineConfig, number>({
      query: (id) => `/pipelines/configs/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'PipelineConfig', id }],
    }),
    createPipelineConfig: builder.mutation<PipelineConfig, PipelineConfigCreate>({
      query: (data) => ({ url: '/pipelines/configs', method: 'POST', body: data }),
      invalidatesTags: ['PipelineConfig'],
    }),
    updatePipelineConfig: builder.mutation<
      PipelineConfig,
      { id: number; data: PipelineConfigUpdate }
    >({
      query: ({ id, data }) => ({ url: `/pipelines/configs/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: 'PipelineConfig', id },
        'PipelineConfig',
      ],
    }),
    deletePipelineConfig: builder.mutation<void, number>({
      query: (id) => ({ url: `/pipelines/configs/${id}`, method: 'DELETE' }),
      invalidatesTags: ['PipelineConfig'],
    }),
    duplicatePipelineConfig: builder.mutation<PipelineConfig, { id: number; name: string }>({
      query: ({ id, name }) => ({
        url: `/pipelines/configs/${id}/duplicate`,
        method: 'POST',
        body: { name },
      }),
      invalidatesTags: ['PipelineConfig'],
    }),

    // ═══════════════════════════════════════════════════════════════════
    // Git Mirroring V2
    // ═══════════════════════════════════════════════════════════════════

    // Source Providers
    getSourceProviders: builder.query<SourceProvider[], void>({
      query: () => '/mirroring/providers',
      providesTags: ['SourceProvider'],
    }),
    createSourceProvider: builder.mutation<SourceProvider, SourceProviderCreate>({
      query: (body) => ({ url: '/mirroring/providers', method: 'POST', body }),
      invalidatesTags: ['SourceProvider'],
    }),
    updateSourceProvider: builder.mutation<
      SourceProvider,
      { id: number; data: SourceProviderUpdate }
    >({
      query: ({ id, data }) => ({
        url: `/mirroring/providers/${id}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: 'SourceProvider', id },
        'SourceProvider',
      ],
    }),
    deleteSourceProvider: builder.mutation<void, number>({
      query: (id) => ({ url: `/mirroring/providers/${id}`, method: 'DELETE' }),
      invalidatesTags: ['SourceProvider'],
    }),

    // Source Groups
    getSourceGroups: builder.query<SourceGroup[], number>({
      query: (providerId) => `/mirroring/providers/${providerId}/groups`,
      providesTags: ['SourceGroup'],
    }),
    importSourceGroup: builder.mutation<SourceGroup, { provider_id: number; group_name: string }>({
      query: ({ provider_id, group_name }) => ({
        url: `/mirroring/providers/${provider_id}/groups/import`,
        method: 'POST',
        params: { group_name },
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

    // Source Repositories
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

    // Mirrors
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

    // Sync Groups
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
      invalidatesTags: (result, error, { id }) => [{ type: 'SyncGroup', id }, 'SyncGroup'],
    }),

    // ──── Orphaned Mirrors ──────────────────────────────────────────────────

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

    checkMirrorIntegrity: builder.mutation<IntegrityCheckResult, number>({
      query: (id) => ({ url: `/mirroring/mirrors/${id}/integrity-check`, method: 'POST' }),
    }),

    // ═══════════════════════════════════════════════════════════════════
    // Reports
    // ═══════════════════════════════════════════════════════════════════

    // ── Duplicates ─────────────────────────────────────────────────────

    getDuplicatesReport: builder.query<DuplicatesReport, void>({
      query: () => '/reports/duplicates',
      providesTags: ['Reports'],
    }),

    // ── Storage ────────────────────────────────────────────────────────

    getStorageReport: builder.query<StorageReport, void>({
      query: () => '/reports/storage',
      providesTags: ['Reports'],
    }),

    refreshStorageReport: builder.mutation<StorageRefreshStatus, void>({
      query: () => ({ url: '/reports/storage/refresh', method: 'POST' }),
      invalidatesTags: ['Reports'],
    }),

    // ── Status ─────────────────────────────────────────────────────────

    getStatusReport: builder.query<StatusReport, { trend_days?: number } | void>({
      query: (params) => ({ url: '/reports/status', params: params ?? undefined }),
      providesTags: ['Reports'],
    }),

    // ── Syncs ──────────────────────────────────────────────────────────

    getSyncsReport: builder.query<
      SyncsReport,
      { period_start?: string; period_end?: string } | void
    >({
      query: (params) => ({ url: '/reports/syncs', params: params ?? undefined }),
      providesTags: ['Reports'],
    }),

    // ── Bulk Operations ────────────────────────────────────────────────

    bulkReassignSyncGroup: builder.mutation<
      BulkOperationResponse,
      { mirror_ids: number[]; sync_group_id: number }
    >({
      query: (body) => ({ url: '/reports/bulk/reassign-sync-group', method: 'POST', body }),
      invalidatesTags: ['Reports', 'Mirror', 'SyncGroup'],
    }),

    bulkChangeTargetGitlab: builder.mutation<
      BulkOperationResponse,
      { mirror_ids: number[]; sync_group_id: number }
    >({
      query: (body) => ({ url: '/reports/bulk/change-target-gitlab', method: 'POST', body }),
      invalidatesTags: ['Reports', 'Mirror', 'SyncGroup'],
    }),

    bulkApplyPipeline: builder.mutation<
      BulkOperationResponse,
      { mirror_ids: number[]; pipeline_id: number }
    >({
      query: (body) => ({ url: '/reports/bulk/apply-pipeline', method: 'POST', body }),
      invalidatesTags: ['Reports', 'Mirror', 'SyncGroup', 'PipelineConfig'],
    }),

    // ──── Audit Logs ────────────────────────────────────────────────────────

    getAuditLogs: builder.query<
      AuditLogList,
      {
        user_id?: number;
        action?: string;
        resource_type?: string;
        date_from?: string;
        date_to?: string;
        page?: number;
        page_size?: number;
      }
    >({
      query: (params) => ({ url: '/admin/audit-logs', params }),
      providesTags: ['AuditLog'],
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
  useGetProjectReleasesQuery,
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
  useScanGoldImageVersionMutation,
  useGetGoldImageScanResultsMutation,
  useSignGoldImageVersionMutation,
  useVerifyGoldImageVersionMutation,
  useListAppImagesQuery,
  useGetAppImageQuery,
  useCreateAppImageMutation,
  useUpdateAppImageMutation,
  useDeleteAppImageMutation,
  useTriggerAppBuildMutation,
  useScanAppImageVersionMutation,
  useSignAppImageVersionMutation,
  useVerifyAppImageVersionMutation,
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
  // Role Scope
  useGetRoleScopeQuery,
  useAddRoleScopeItemMutation,
  useSetRoleScopeMutation,
  useRemoveRoleScopeItemMutation,
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
  useBatchDeleteDockerTagsMutation,
  useAnalyzeDockerImageMutation,
  useGetDockerSyncSchedulesQuery,
  useCompareDockerImagesQuery,
  useCreateDockerSyncScheduleMutation,
  useUpdateDockerSyncScheduleMutation,
  useDeleteDockerSyncScheduleMutation,
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
  useGetPipelineRunsQuery,
  useGetPipelineRunQuery,
  useTriggerPipelineMutation,
  useCancelPipelineMutation,
  useRetryPipelineMutation,
  useGetComponentsQuery,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
  useRunComponentMutation,
  useGetAuditLogsQuery,
  // Git Mirroring V2
  useGetSourceProvidersQuery,
  useCreateSourceProviderMutation,
  useUpdateSourceProviderMutation,
  useDeleteSourceProviderMutation,
  useGetSourceGroupsQuery,
  useImportSourceGroupMutation,
  useGetSourceGroupQuery,
  useRefreshSourceGroupMutation,
  useDeleteSourceGroupMutation,
  useGetSourceRepositoriesQuery,
  useGetSourceRepositoryQuery,
  useGetRepositoryReleasesQuery,
  useGetRepositoryReadmeQuery,
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
  useGetSyncGroupsQuery,
  useCreateSyncGroupMutation,
  useGetSyncGroupQuery,
  useUpdateSyncGroupMutation,
  useDeleteSyncGroupMutation,
  useAssignMirrorsToGroupMutation,
  useApplyPipelineToGroupMutation,
  // Orphaned Mirrors
  useGetOrphanedMirrorsQuery,
  useReassignOrphanedMirrorMutation,
  useMoveOrphanedTargetMutation,
  useDeleteOrphanedMirrorMutation,
  useCheckMirrorIntegrityMutation,
  // Pipeline Configurations
  useGetPipelineConfigsQuery,
  useGetPipelineConfigQuery,
  useCreatePipelineConfigMutation,
  useUpdatePipelineConfigMutation,
  useDeletePipelineConfigMutation,
  useDuplicatePipelineConfigMutation,
  // Reports
  useGetDuplicatesReportQuery,
  useGetStorageReportQuery,
  useRefreshStorageReportMutation,
  useGetStatusReportQuery,
  useGetSyncsReportQuery,
  useBulkReassignSyncGroupMutation,
  useBulkChangeTargetGitlabMutation,
  useBulkApplyPipelineMutation,
} = api;
