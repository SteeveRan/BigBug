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
import './api/mirrors-legacy';
import './api/gold-images';
import './api/app-images';
import './api/helm-charts';
import './api/docker-images';
import './api/admin-users';
import './api/admin-rbac';
import './api/integrations';
import './api/oidc-config';
import './api/pipelines';
import './api/pipeline-configs';
import './api/components';
import './api/git-mirroring';
import './api/reports';
import './api/audit-logs';

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

// Mirrors (legacy)
export {
  useListMirrorsQuery,
  useGetMirrorQuery,
  useCreateMirrorMutation,
  useImportMirrorMutation,
  useTriggerSyncMutation,
  useGetMirrorLogsQuery,
  useGetMirrorScheduleQuery,
  useUpdateMirrorScheduleMutation,
} from './api/mirrors-legacy';

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
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
} from './api/helm-charts';

// Docker Images
export {
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

// Integrations
export {
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
} from './api/integrations';

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
} from './api/pipeline-configs';

// GitLab Components
export {
  useGetComponentsQuery,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
  useRunComponentMutation,
} from './api/components';

// Git Mirroring V2 — Source Providers
export {
  useGetSourceProvidersQuery,
  useCreateSourceProviderMutation,
  useUpdateSourceProviderMutation,
  useDeleteSourceProviderMutation,
} from './api/git-mirroring/providers';

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
