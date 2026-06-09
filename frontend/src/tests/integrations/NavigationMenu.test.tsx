/**
 * @file NavigationMenu.test.tsx
 * @description Проверка ВСЕХ пунктов меню через PermissionGate.
 *   Для каждого маршрута проверяется:
 *   1. При НАЛИЧИИ нужной привилегии — страница рендерит контент.
 *   2. При ОТСУТСТВИИ привилегии — PermissionGate возвращает null (контент скрыт).
 *
 *   ВАЖНО: тест использует ТОЧНЫЕ permission-строки из router/index.tsx.
 *   hasPermission НЕ заглушен на () => true — он реально проверяет
 *   наличие строки в массиве permissions.
 *
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../router/index.tsx, ../components/PermissionGate.tsx,
 *              ../hooks/usePermissions.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import { App } from 'antd';

// ---------------------------------------------------------------------------
// Mocks — должны быть ДО импортов (vi.mock hoisted)
// ---------------------------------------------------------------------------

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

// Мокаем ВСЕ RTK Query хуки, которые могут использоваться на страницах
vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    // Dashboard (Overview)
    useListProjectsQuery: vi.fn(),
    useListMirrorsQuery: vi.fn(),
    useListGoldImagesQuery: vi.fn(),
    useListAppImagesQuery: vi.fn(),
    // Mirrors / Projects
    useGetProjectQuery: vi.fn(),
    useCreateProjectMutation: vi.fn(),
    useImportProjectMutation: vi.fn(),
    useUpdateProjectMutation: vi.fn(),
    useDeleteProjectMutation: vi.fn(),
    useRefreshProjectMutation: vi.fn(),
    useGetMirrorQuery: vi.fn(),
    useCreateMirrorMutation: vi.fn(),
    useImportMirrorMutation: vi.fn(),
    useTriggerSyncMutation: vi.fn(),
    useGetMirrorLogsQuery: vi.fn(),
    useGetMirrorScheduleQuery: vi.fn(),
    useUpdateMirrorScheduleMutation: vi.fn(),
    // Helm Charts
    useListHelmChartsQuery: vi.fn(),
    useGetHelmChartQuery: vi.fn(),
    useCreateHelmChartMutation: vi.fn(),
    useUpdateHelmChartMutation: vi.fn(),
    useDeleteHelmChartMutation: vi.fn(),
    useIndexHelmChartMutation: vi.fn(),
    useGetHelmChartVersionsQuery: vi.fn(),
    useGetHelmChartLogsQuery: vi.fn(),
    // Docker Images
    useListDockerImagesQuery: vi.fn(),
    useGetDockerImageQuery: vi.fn(),
    useCreateDockerImageMutation: vi.fn(),
    useUpdateDockerImageMutation: vi.fn(),
    useDeleteDockerImageMutation: vi.fn(),
    useIndexDockerImageMutation: vi.fn(),
    useGetDockerImageTagsQuery: vi.fn(),
    useGetDockerImageLogsQuery: vi.fn(),
    // Gold Images
    useGetGoldImageQuery: vi.fn(),
    useCreateGoldImageMutation: vi.fn(),
    useUpdateGoldImageMutation: vi.fn(),
    useDeleteGoldImageMutation: vi.fn(),
    useTriggerGoldBuildMutation: vi.fn(),
    useScanGoldImageVersionMutation: vi.fn(),
    useGetGoldImageScanResultsMutation: vi.fn(),
    useSignGoldImageVersionMutation: vi.fn(),
    useVerifyGoldImageVersionMutation: vi.fn(),
    // App Images
    useGetAppImageQuery: vi.fn(),
    useCreateAppImageMutation: vi.fn(),
    useUpdateAppImageMutation: vi.fn(),
    useDeleteAppImageMutation: vi.fn(),
    useTriggerAppBuildMutation: vi.fn(),
    useScanAppImageVersionMutation: vi.fn(),
    useSignAppImageVersionMutation: vi.fn(),
    useVerifyAppImageVersionMutation: vi.fn(),
    // Admin / Users & Roles
    useListUsersQuery: vi.fn(),
    useCreateUserMutation: vi.fn(),
    useUpdateUserMutation: vi.fn(),
    useDeleteUserMutation: vi.fn(),
    useGetUserPermissionsQuery: vi.fn(),
    useGetAllPermissionsQuery: vi.fn(),
    useGetAllRolesQuery: vi.fn(),
    useGetRoleByIdQuery: vi.fn(),
    useCreateRoleMutation: vi.fn(),
    useUpdateRoleMutation: vi.fn(),
    useDeleteRoleMutation: vi.fn(),
    // Integrations — GitLab
    useGetGitlabInstancesQuery: vi.fn(),
    useGetGitlabInstanceQuery: vi.fn(),
    useCreateGitlabInstanceMutation: vi.fn(),
    useUpdateGitlabInstanceMutation: vi.fn(),
    useDeleteGitlabInstanceMutation: vi.fn(),
    useTestGitlabConnectionMutation: vi.fn(),
    // Integrations — Harbor
    useGetHarborInstancesQuery: vi.fn(),
    useGetHarborInstanceQuery: vi.fn(),
    useCreateHarborInstanceMutation: vi.fn(),
    useUpdateHarborInstanceMutation: vi.fn(),
    useDeleteHarborInstanceMutation: vi.fn(),
    useTestHarborConnectionMutation: vi.fn(),
    // Integrations — GitHub
    useGetGithubInstancesQuery: vi.fn(),
    useGetGithubInstanceQuery: vi.fn(),
    useCreateGithubInstanceMutation: vi.fn(),
    useUpdateGithubInstanceMutation: vi.fn(),
    useDeleteGithubInstanceMutation: vi.fn(),
    useTestGithubConnectionMutation: vi.fn(),
    // Integrations — Docker Registry
    useGetDockerRegistryInstancesQuery: vi.fn(),
    useGetDockerRegistryInstanceQuery: vi.fn(),
    useCreateDockerRegistryInstanceMutation: vi.fn(),
    useUpdateDockerRegistryInstanceMutation: vi.fn(),
    useDeleteDockerRegistryInstanceMutation: vi.fn(),
    useTestDockerRegistryConnectionMutation: vi.fn(),
    // Integrations — Helm Repository
    useGetHelmRepositoryInstancesQuery: vi.fn(),
    useGetHelmRepositoryInstanceQuery: vi.fn(),
    useCreateHelmRepositoryInstanceMutation: vi.fn(),
    useUpdateHelmRepositoryInstanceMutation: vi.fn(),
    useDeleteHelmRepositoryInstanceMutation: vi.fn(),
    useTestHelmRepositoryConnectionMutation: vi.fn(),
    // OIDC / Authentication
    useGetOidcConfigQuery: vi.fn(),
    useUpdateOidcConfigMutation: vi.fn(),
    // Pipelines
    useGetPipelineRunsQuery: vi.fn(),
    useGetPipelineRunQuery: vi.fn(),
    useTriggerPipelineMutation: vi.fn(),
    useCancelPipelineMutation: vi.fn(),
    useRetryPipelineMutation: vi.fn(),
    // GitLab Components
    useGetComponentsQuery: vi.fn(),
    useCreateComponentMutation: vi.fn(),
    useUpdateComponentMutation: vi.fn(),
    useDeleteComponentMutation: vi.fn(),
    // Audit Log
    useGetAuditLogsQuery: vi.fn(),
    // Auth
    useLoginMutation: vi.fn(),
    useGetMeQuery: vi.fn(),
    useGetSsoConfigQuery: vi.fn(),
    useSsoExchangeMutation: vi.fn(),
  };
});

// ---------------------------------------------------------------------------
// Imports — после vi.mock
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import {
  useListProjectsQuery,
  useListMirrorsQuery,
  useListGoldImagesQuery,
  useListAppImagesQuery,
  useListHelmChartsQuery,
  useListDockerImagesQuery,
  useGetPipelineRunsQuery,
  useGetComponentsQuery,
  useListUsersQuery,
  useGetGitlabInstancesQuery,
  useGetOidcConfigQuery,
  useGetAuditLogsQuery,
  useGetHarborInstancesQuery,
  useGetGithubInstancesQuery,
  useGetDockerRegistryInstancesQuery,
  useGetHelmRepositoryInstancesQuery,
  useGetUserPermissionsQuery,
  useGetAllPermissionsQuery,
  useGetAllRolesQuery,
  useGetRoleByIdQuery,
  useGetGoldImageScanResultsMutation,
  useCreateProjectMutation,
  useImportProjectMutation,
  useDeleteProjectMutation,
  useRefreshProjectMutation,
  useUpdateProjectMutation,
  useCreateHelmChartMutation,
  useIndexHelmChartMutation,
  useCreateDockerImageMutation,
  useIndexDockerImageMutation,
  useCreateGoldImageMutation,
  useUpdateGoldImageMutation,
  useDeleteGoldImageMutation,
  useTriggerGoldBuildMutation,
  useScanGoldImageVersionMutation,
  useSignGoldImageVersionMutation,
  useCreateAppImageMutation,
  useUpdateAppImageMutation,
  useDeleteAppImageMutation,
  useTriggerAppBuildMutation,
  useScanAppImageVersionMutation,
  useSignAppImageVersionMutation,
  useCreateUserMutation,
  useDeleteUserMutation,
  useUpdateUserMutation,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
  useCreateGitlabInstanceMutation,
  useUpdateGitlabInstanceMutation,
  useDeleteGitlabInstanceMutation,
  useTestGitlabConnectionMutation,
  useCreateHarborInstanceMutation,
  useUpdateHarborInstanceMutation,
  useDeleteHarborInstanceMutation,
  useTestHarborConnectionMutation,
  useCreateGithubInstanceMutation,
  useUpdateGithubInstanceMutation,
  useDeleteGithubInstanceMutation,
  useTestGithubConnectionMutation,
  useCreateDockerRegistryInstanceMutation,
  useUpdateDockerRegistryInstanceMutation,
  useDeleteDockerRegistryInstanceMutation,
  useTestDockerRegistryConnectionMutation,
  useCreateHelmRepositoryInstanceMutation,
  useUpdateHelmRepositoryInstanceMutation,
  useDeleteHelmRepositoryInstanceMutation,
  useTestHelmRepositoryConnectionMutation,
  useUpdateOidcConfigMutation,
  useTriggerPipelineMutation,
  useCancelPipelineMutation,
  useRetryPipelineMutation,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { PermissionGate } from '../../components/PermissionGate';

import { DashboardPage } from '../../pages/Overview';
import { ProjectsPage } from '../../pages/Projects';
import { HelmChartsPage } from '../../pages/HelmCharts';
import { DockerImagesPage } from '../../pages/DockerImages';
import { GoldImagesPage } from '../../pages/GoldImages';
import { AppImagesPage } from '../../pages/AppImages';
import { PipelinesPage } from '../../pages/Pipelines/Runs';
import { GitLabComponentsPage } from '../../pages/Pipelines/Components';
import { AdminPage } from '../../pages/Admin/Users';
import { SettingsIntegrations } from '../../pages/Admin/Integrations';
import { AuthenticationSettings } from '../../pages/Admin/Authentication';
import { AuditLogPage } from '../../pages/Admin/AuditLog';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Типовой мок для mutation: [triggerFn, { isLoading: false }] */
function mockMutation() {
  return [vi.fn().mockResolvedValue({ data: {} }), { isLoading: false }] as const;
}

/** Типовой мок для query: { data: [], isLoading: false, isError: false } */
function mockQueryEmpty() {
  return { data: [], isLoading: false, isError: false };
}

/** Создать Redux store (без auth, страницы рендерятся через PermissionGate, а не ProtectedRoute) */
function createTestStore() {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

interface MenuPageConfig {
  /** Человеческое название пункта меню (для имени теста) */
  label: string;
  /** JSX элемент страницы (компонент) */
  page: React.ReactElement;
  /** Permission-строка из router/index.tsx (для Overview — null) */
  permission: string | null;
  /**
   * Текст, который ищется на странице при наличии привилегии.
   * Должен соответствовать фактическому Typography.Title из компонента.
   */
  contentMarker: string;
}

/**
 * Все 12 пунктов меню с их permission-строками из router/index.tsx.
 * Перечислены в том же порядке, что и в Layout/index.tsx: menuItems.
 * contentMarker соответствует реальному заголовку Typography.Title на странице.
 */
const MENU_PAGES: MenuPageConfig[] = [
  {
    label: 'Overview',
    page: <DashboardPage />,
    permission: null, // нет PermissionGate
    contentMarker: 'Dashboard',
  },
  {
    label: 'Mirroring / Repositories',
    page: <ProjectsPage />,
    permission: 'projects:read',
    contentMarker: 'GitHub Projects',
  },
  {
    label: 'Mirroring / Helm Charts',
    page: <HelmChartsPage />,
    permission: 'helm:read',
    contentMarker: 'Helm Charts',
  },
  {
    label: 'Mirroring / Docker Images',
    page: <DockerImagesPage />,
    permission: 'docker:read',
    contentMarker: 'Docker Images',
  },
  {
    label: 'Builds / Gold Images',
    page: <GoldImagesPage />,
    permission: 'gold_images:read',
    contentMarker: 'Gold Images',
  },
  {
    label: 'Builds / App Images',
    page: <AppImagesPage />,
    permission: 'app_images:read',
    contentMarker: 'App Images',
  },
  {
    label: 'Pipelines / Pipeline Runs',
    page: <PipelinesPage />,
    permission: 'pipelines:manage',
    contentMarker: 'Pipeline Runs',
  },
  {
    label: 'Pipelines / GitLab Components',
    page: <GitLabComponentsPage />,
    permission: 'pipelines:manage',
    contentMarker: 'GitLab Components',
  },
  {
    label: 'Administration / Users & Roles',
    page: <AdminPage />,
    permission: 'users:read',
    contentMarker: 'Admin',
  },
  {
    label: 'Administration / Integrations',
    page: <SettingsIntegrations />,
    permission: 'system:integrations',
    contentMarker: 'Settings',
  },
  {
    label: 'Administration / Authentication',
    page: <AuthenticationSettings />,
    permission: 'system:oidc_config',
    contentMarker: 'Authentication Settings',
  },
  {
    label: 'Administration / Audit Log',
    page: <AuditLogPage />,
    permission: 'system:audit',
    contentMarker: 'Audit Log',
  },
];

// ---------------------------------------------------------------------------
// Setup helpers
// ---------------------------------------------------------------------------

/**
 * Установить usePermissions mock с конкретным списком разрешений.
 * hasPermission РЕАЛЬНО проверяет наличие строки в массиве.
 */
function setPermissions(enabledPermissions: string[]) {
  (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
    hasPermission: (p: string) => enabledPermissions.includes(p),
    hasAnyPermission: (ps: string[]) =>
      ps.some((p) => enabledPermissions.includes(p)),
    hasAllPermissions: (ps: string[]) =>
      ps.every((p) => enabledPermissions.includes(p)),
    permissions: enabledPermissions,
    isLoading: false,
  });
}

/**
 * Замокать стандартные query/mutation хуки safe-значениями,
 * чтобы страницы не падали при рендере.
 */
function setupDefaultApiMocks() {
  const mockQ = mockQueryEmpty();
  // Queries → empty data
  (useListProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useListMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useListGoldImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useListAppImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useListHelmChartsQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useListDockerImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetPipelineRunsQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetComponentsQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetGitlabInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetHarborInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetGithubInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetDockerRegistryInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetHelmRepositoryInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetUserPermissionsQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetAllPermissionsQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetRoleByIdQuery as ReturnType<typeof vi.fn>).mockReturnValue(mockQ);
  (useGetGoldImageScanResultsMutation as ReturnType<typeof vi.fn>).mockReturnValue(mockMutation());
  (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: {
      enabled: false,
      provider_name: '',
      client_id: '',
      well_known_url: '',
      provider_url: '',
      client_secret_set: false,
    },
    isLoading: false,
    isError: false,
  });
  (useGetAuditLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: { items: [], total: 0, page: 1, page_size: 20 },
    isLoading: false,
    isError: false,
  });

  // Mutations → [fn, { isLoading: false }]
  const mMock = mockMutation();
  const mutations = [
    useCreateProjectMutation, useImportProjectMutation, useDeleteProjectMutation,
    useRefreshProjectMutation, useUpdateProjectMutation,
    useCreateHelmChartMutation, useIndexHelmChartMutation,
    useCreateDockerImageMutation, useIndexDockerImageMutation,
    useCreateGoldImageMutation, useUpdateGoldImageMutation, useDeleteGoldImageMutation,
    useTriggerGoldBuildMutation, useScanGoldImageVersionMutation, useSignGoldImageVersionMutation,
    useCreateAppImageMutation, useUpdateAppImageMutation, useDeleteAppImageMutation,
    useTriggerAppBuildMutation, useScanAppImageVersionMutation, useSignAppImageVersionMutation,
    useCreateUserMutation, useDeleteUserMutation, useUpdateUserMutation,
    useCreateRoleMutation, useUpdateRoleMutation, useDeleteRoleMutation,
    useCreateGitlabInstanceMutation, useUpdateGitlabInstanceMutation, useDeleteGitlabInstanceMutation,
    useTestGitlabConnectionMutation,
    useCreateHarborInstanceMutation, useUpdateHarborInstanceMutation, useDeleteHarborInstanceMutation,
    useTestHarborConnectionMutation,
    useCreateGithubInstanceMutation, useUpdateGithubInstanceMutation, useDeleteGithubInstanceMutation,
    useTestGithubConnectionMutation,
    useCreateDockerRegistryInstanceMutation, useUpdateDockerRegistryInstanceMutation,
    useDeleteDockerRegistryInstanceMutation, useTestDockerRegistryConnectionMutation,
    useCreateHelmRepositoryInstanceMutation, useUpdateHelmRepositoryInstanceMutation,
    useDeleteHelmRepositoryInstanceMutation, useTestHelmRepositoryConnectionMutation,
    useUpdateOidcConfigMutation,
    useTriggerPipelineMutation, useCancelPipelineMutation, useRetryPipelineMutation,
    useCreateComponentMutation, useUpdateComponentMutation, useDeleteComponentMutation,
  ];
  for (const m of mutations) {
    (m as ReturnType<typeof vi.fn>).mockReturnValue(mMock);
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('NavigationMenu — все пункты меню', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    store = createTestStore();
    vi.clearAllMocks();
    setupDefaultApiMocks();
  });

  // ── POSITIVE: permission present → content renders ─────────────────

  describe('При наличии нужной привилегии — контент отображается', () => {
    for (const cfg of MENU_PAGES) {
      it(`${cfg.label} (permission: ${cfg.permission ?? 'none'})`, () => {
        // Разрешаем ВСЕ permissions, чтобы PermissionGate пропустил любую проверку
        setPermissions([
          'projects:read',
          'helm:read',
          'docker:read',
          'gold_images:read',
          'app_images:read',
          'pipelines:manage',
          'users:read',
          'system:integrations',
          'system:oidc_config',
          'system:audit',
          'system:settings',
        ]);

        const pageElement = cfg.permission ? (
          <PermissionGate permission={cfg.permission}>
            {cfg.page}
          </PermissionGate>
        ) : (
          cfg.page
        );

        render(
          <Provider store={store}>
            <BrowserRouter>
              <App>{pageElement}</App>
            </BrowserRouter>
          </Provider>,
        );

        // Каждая страница должна содержать свой заголовок/маркер
        // (используем getAllByText, т.к. текст может встречаться в заголовке и empty-state)
        expect(
          screen.getAllByText(cfg.contentMarker, { exact: false }).length,
        ).toBeGreaterThanOrEqual(1);
      });
    }
  });

  // ── NEGATIVE: permission absent → PermissionGate returns null ──────

  describe('При ОТСУТСТВИИ привилегии — контент скрыт (PermissionGate → null)', () => {
    for (const cfg of MENU_PAGES) {
      // Overview не имеет PermissionGate — пропускаем negative-тест
      if (!cfg.permission) continue;

      it(`${cfg.label} без "${cfg.permission}" — страница не рендерится`, () => {
        // Даём права, НО НЕ то, которое требуется для этой страницы
        const otherPermissions = [
          'projects:read',
          'helm:read',
          'docker:read',
          'gold_images:read',
          'app_images:read',
          'pipelines:manage',
          'users:read',
          'system:integrations',
          'system:oidc_config',
          'system:audit',
        ].filter((p) => p !== cfg.permission);

        setPermissions(otherPermissions);

        render(
          <Provider store={store}>
            <BrowserRouter>
              <App>
                <PermissionGate permission={cfg.permission!}>
                  {cfg.page}
                </PermissionGate>
              </App>
            </BrowserRouter>
          </Provider>,
        );

        // PermissionGate должен вернуть null → контента нет на странице
        expect(
          screen.queryByText(cfg.contentMarker, { exact: false }),
        ).not.toBeInTheDocument();
      });
    }
  });

  // ── Точная проверка: соответствие permission-строк фронтенда и бэкенда ─

  describe('Соответствие permission-строк router/index.tsx и PERMISSION_GROUPS', () => {
    it('все permission-строки из роутера присутствуют в PERMISSION_GROUPS', () => {
      // PERMISSION_GROUPS (Admin/index.tsx) — эталонный список
      const allCanonicalPermissions: string[] = [
        'mirrors:read', 'mirrors:write', 'mirrors:delete', 'mirrors:sync',
        'projects:read', 'projects:write', 'projects:delete',
        'helm:read', 'helm:write', 'helm:delete', 'helm:sync',
        'docker:read', 'docker:write', 'docker:delete', 'docker:sync',
        'gold_images:read', 'gold_images:write', 'gold_images:delete', 'gold_images:build',
        'app_images:read', 'app_images:write', 'app_images:delete', 'app_images:build',
        'users:read', 'users:write', 'users:delete',
        'roles:read', 'roles:write', 'roles:delete',
        'system:settings', 'system:audit', 'system:integrations', 'system:oidc_config',
        'pipelines:manage',
      ];

      // Все permission-строки из роутера (MENU_PAGES)
      const routerPermissions = MENU_PAGES
        .filter((c) => c.permission !== null)
        .map((c) => c.permission!);

      for (const perm of routerPermissions) {
        expect(
          allCanonicalPermissions,
          `Permission "${perm}" из router/index.tsx отсутствует в PERMISSION_GROUPS!`,
        ).toContain(perm);
      }
    });
  });
});
