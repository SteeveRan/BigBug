/**
 * @file api.ts
 * @description Центральный API-слайс — единая точка входа. Импортирует все инжекторы эндпоинтов
 *              и реэкспортирует сгенерированные хуки. Приложение использует только этот файл.
 * @dependencies api/base.ts, все файлы в api/ и api/git-mirroring/
 */

// Реэкспорт базового API-объекта (используется в store/index.ts + тестах)
export { api } from './api/base';

// Побочные импорты — регистрируют эндпоинты через injectEndpoints.
// Порядок не важен, каждый файл самодостаточен.
import './api/auth';
import './api/projects-legacy';
import './api/gold-images';
import './api/app-images';
import './api/helm-charts';
import './api/docker-images';
import './api/admin-users';
import './api/admin-rbac';
import './api/oidc-config';
import './api/pipelines';
import './api/pipeline-configs';
import './api/components';
import './api/git-mirroring';
import './api/reports';
import './api/audit-logs';
import './api/providers';
import './api/teams';
import './api/credentials';
import './api/gitlab-projects';

// ═════════════════════════════════════════════════════════════════════════
// Реэкспорт ВСЕХ хуков — чтобы потребители (страницы, компоненты, тесты)
// продолжали импортировать из '../../store/api' без изменений.
// ═════════════════════════════════════════════════════════════════════════

// Auth
export {
  useLoginMutation,
  useGetMeQuery,
  useGetUserPermissionsQuery,
  useGetSsoConfigQuery,
  useSsoExchangeMutation,
} from './api/auth';

// Projects (legacy)
export {
  useListProjectsQuery,
  useGetProjectQuery,
  useCreateProjectMutation,
  useImportProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
  useRefreshProjectMutation,
  useGetProjectReleasesQuery,
} from './api/projects-legacy';

// Gold Images
export {
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
} from './api/gold-images';

// App Images
export {
  useListAppImagesQuery,
  useGetAppImageQuery,
  useCreateAppImageMutation,
  useUpdateAppImageMutation,
  useDeleteAppImageMutation,
  useTriggerAppBuildMutation,
  useScanAppImageVersionMutation,
  useSignAppImageVersionMutation,
  useVerifyAppImageVersionMutation,
} from './api/app-images';

// Helm Charts
export {
  useListHelmChartsQuery,
  useGetHelmChartQuery,
  useCreateHelmChartMutation,
  useUpdateHelmChartMutation,
  useDeleteHelmChartMutation,
  useIndexHelmChartMutation,
  useMirrorHelmChartMutation,
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
  useGetHelmSyncSchedulesQuery,
  useCreateHelmSyncScheduleMutation,
  useUpdateHelmSyncScheduleMutation,
  useDeleteHelmSyncScheduleMutation,
} from './api/helm-charts';

// Docker Images
export {
  useListDockerImagesQuery,
  useGetDockerImageQuery,
  useCreateDockerImageMutation,
  useUpdateDockerImageMutation,
  useDeleteDockerImageMutation,
  useIndexDockerImageMutation,
  useMirrorDockerImageMutation,
  useGetDockerImageTagsQuery,
  useGetDockerImageLogsQuery,
  useBatchDeleteDockerTagsMutation,
  useAnalyzeDockerImageMutation,
  useCompareDockerImagesQuery,
  useGetDockerSyncSchedulesQuery,
  useCreateDockerSyncScheduleMutation,
  useUpdateDockerSyncScheduleMutation,
  useDeleteDockerSyncScheduleMutation,
} from './api/docker-images';

// Admin: Users
export {
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
} from './api/admin-users';

// Admin: RBAC
export {
  useGetAllPermissionsQuery,
  useGetAllRolesQuery,
  useGetRoleByIdQuery,
  useGetRoleUsersQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
  useGetRoleScopeQuery,
  useAddRoleScopeItemMutation,
  useSetRoleScopeMutation,
  useRemoveRoleScopeItemMutation,
} from './api/admin-rbac';

// OIDC Config
export { useGetOidcConfigQuery, useUpdateOidcConfigMutation } from './api/oidc-config';

// Pipeline Runs
export {
  useGetPipelineRunsQuery,
  useGetPipelineRunQuery,
  useTriggerPipelineMutation,
  useCancelPipelineMutation,
  useRetryPipelineMutation,
} from './api/pipelines';

// Pipeline Configurations
export {
  useGetPipelineConfigsQuery,
  useGetPipelineConfigQuery,
  useCreatePipelineConfigMutation,
  useUpdatePipelineConfigMutation,
  useDeletePipelineConfigMutation,
  useDuplicatePipelineConfigMutation,
  usePushPipelineCiMutation,
  useRunPipelineConfigMutation,
} from './api/pipeline-configs';

// GitLab Components
export {
  useGetComponentsQuery,
  useGetComponentPresetsQuery,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
  usePushComponentMutation,
  usePullComponentMutation,
  useRunComponentMutation,
} from './api/components';

// GitLab Projects
export {
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
} from './api/gitlab-projects';

// Git Mirroring V2 — Source Groups
export {
  useGetSourceGroupsQuery,
  useImportSourceGroupMutation,
  useGetSourceGroupQuery,
  useRefreshSourceGroupMutation,
  useDeleteSourceGroupMutation,
} from './api/git-mirroring/groups';

// Git Mirroring V2 — Source Repositories
export {
  useGetSourceRepositoriesQuery,
  useGetSourceRepositoryQuery,
  useGetRepositoryReleasesQuery,
  useGetRepositoryReadmeQuery,
  useCreateSourceRepositoryMutation,
  useDeleteSourceRepositoryMutation,
  useRefreshSourceRepositoryMutation,
} from './api/git-mirroring/repositories';

// Git Mirroring V2 — Mirrors
export {
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
  useCheckMirrorIntegrityMutation,
} from './api/git-mirroring/mirrors';

// Git Mirroring V2 — Sync Groups
export {
  useGetSyncGroupsQuery,
  useCreateSyncGroupMutation,
  useGetSyncGroupQuery,
  useUpdateSyncGroupMutation,
  useDeleteSyncGroupMutation,
  useAssignMirrorsToGroupMutation,
  useApplyPipelineToGroupMutation,
} from './api/git-mirroring/sync-groups';

// Git Mirroring V2 — Orphaned Mirrors
export {
  useGetOrphanedMirrorsQuery,
  useReassignOrphanedMirrorMutation,
  useMoveOrphanedTargetMutation,
  useDeleteOrphanedMirrorMutation,
} from './api/git-mirroring/orphaned';

// Reports
export {
  useGetDuplicatesReportQuery,
  useGetStorageReportQuery,
  useRefreshStorageReportMutation,
  useGetStatusReportQuery,
  useGetSyncsReportQuery,
  useBulkReassignSyncGroupMutation,
  useBulkChangeTargetGitlabMutation,
  useBulkApplyPipelineMutation,
} from './api/reports';

// Audit Logs
export { useGetAuditLogsQuery } from './api/audit-logs';

// Providers V3
export {
  useGetProviderTypesQuery,
  useGetProvidersQuery,
  useGetProviderQuery,
  useCreateProviderMutation,
  useUpdateProviderMutation,
  useDeleteProviderMutation,
  useTestProviderMutation,
  useRunProviderActionMutation,
  useGetProviderUsageQuery,
  useShareProviderMutation,
  useUnshareProviderMutation,
} from './api/providers';

// Teams
export {
  useGetTeamsQuery,
  useCreateTeamMutation,
  useUpdateTeamMutation,
  useDeleteTeamMutation,
  useGetTeamMembersQuery,
  useAddTeamMemberMutation,
  useRemoveTeamMemberMutation,
  useGetTeamProvidersQuery,
} from './api/teams';

// Credentials
export {
  useGetCredentialsQuery,
  useCreateCredentialMutation,
  useUpdateCredentialMutation,
  useDeleteCredentialMutation,
  useTestCredentialMutation,
} from './api/credentials';
