import { lazy } from 'react';
import { Routes, Route, Navigate, useParams } from 'react-router';
import { useAppSelector } from '../store';
import { Layout } from '../components/Layout';
import { ProtectedRoute } from './ProtectedRoute';
import { PermissionGate } from '../components/PermissionGate';
import { LoginPage } from '../pages/Login';
import { SsoCallbackPage } from '../pages/SsoCallback';
import { DashboardPage } from '../pages/Overview';
import { ProjectsPage, ProjectDetailPage } from '../pages/Mirroring/Repositories';
import { HelmChartsPage, HelmChartDetailPage } from '../pages/Mirroring/HelmCharts';
import { DockerImagesPage, DockerImageDetailPage, DockerImageComparePage } from '../pages/Mirroring/DockerImages';
import { GoldImagesPage } from '../pages/Builds/GoldImages';
import { AppImagesPage } from '../pages/Builds/AppImages';
import { PipelinesPage } from '../pages/Pipelines/Runs';
import { GitLabComponentsPage } from '../pages/Pipelines/Components';
import { AdminPage } from '../pages/Admin/Users';
import { SettingsIntegrations } from '../pages/Admin/Integrations';
import { AuthenticationSettings } from '../pages/Admin/Authentication';
import { AuditLogPage } from '../pages/Admin/AuditLog';
import GitMirroring from '../pages/GitMirroring';

// Git Mirroring V2 lazy imports
const GitMirroringMirrors = lazy(() => import('@/pages/GitMirroring/Mirrors'));
const GitMirroringRepositories = lazy(() => import('@/pages/GitMirroring/Repositories'));
const GitMirroringRepositoryDetail = lazy(() => import('@/pages/GitMirroring/Repositories/Detail'));
const GitMirroringProviders = lazy(() => import('@/pages/GitMirroring/Providers'));
const GitMirroringGroups = lazy(() => import('@/pages/GitMirroring/Groups'));
const GitMirroringSyncGroups = lazy(() => import('@/pages/GitMirroring/SyncGroups'));
const PipelineConfigsPage = lazy(() => import('@/pages/Pipelines/Configurations'));

/**
 * @file router/index.tsx
 * @description Новый роутинг BigBug с реорганизованной навигацией.
 *              Новые URL-пути сгруппированы по логическим разделам:
 *              Overview, Mirroring, Builds, Pipelines, Administration.
 *              Старые URL редиректят на новые через <Navigate>.
 *              Каждый route обёрнут в PermissionGate с соответствующим permission.
 * @dependencies react-router, ../components/Layout, ../components/PermissionGate
 * @relatedFiles ../components/Layout/index.tsx, ../pages/*
 */

// ── Redirect helpers for routes with URL params ──────────────
function RedirectProjectsId() {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={`/mirroring/repositories/${id}`} replace />;
}

function RedirectHelmChartsId() {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={`/mirroring/helm-charts/${id}`} replace />;
}

function RedirectDockerImagesId() {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={`/mirroring/docker-images/${id}`} replace />;
}

function RedirectMirrorsId() {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={`/mirroring/repositories/${id}`} replace />;
}

export function AppRouter() {
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated);

  return (
    <Routes>
      {/* ── Public routes (no auth required) ───────────────── */}
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/overview" replace /> : <LoginPage />}
      />
      <Route path="/sso/callback" element={<SsoCallbackPage />} />
      <Route path="/auth/callback" element={<SsoCallbackPage />} />

      {/* ── Protected routes (inside Layout) ──────────────── */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        {/* ── Overview ──────────────────────────────────── */}
        <Route path="overview" element={<DashboardPage />} />
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="dashboard" element={<Navigate to="/overview" replace />} />

        {/* ── Mirroring / Repositories ──────────────────── */}
        <Route
          path="mirroring/repositories"
          element={
            <PermissionGate permission="projects:read">
              <ProjectsPage />
            </PermissionGate>
          }
        />
        <Route
          path="mirroring/repositories/:id"
          element={
            <PermissionGate permission="projects:read">
              <ProjectDetailPage />
            </PermissionGate>
          }
        />

        {/* ── Mirroring / Helm Charts ───────────────────── */}
        <Route
          path="mirroring/helm-charts"
          element={
            <PermissionGate permission="helm:read">
              <HelmChartsPage />
            </PermissionGate>
          }
        />
        <Route
          path="mirroring/helm-charts/:id"
          element={
            <PermissionGate permission="helm:read">
              <HelmChartDetailPage />
            </PermissionGate>
          }
        />

        {/* ── Mirroring / Docker Images ─────────────────── */}
        <Route
          path="mirroring/docker-images"
          element={
            <PermissionGate permission="docker:read">
              <DockerImagesPage />
            </PermissionGate>
          }
        />
        <Route
          path="mirroring/docker-images/:id"
          element={
            <PermissionGate permission="docker:read">
              <DockerImageDetailPage />
            </PermissionGate>
          }
        />

        {/* ── Mirroring / Docker Images / Compare ─────────── */}
        <Route
          path="mirroring/docker-images/compare"
          element={
            <PermissionGate permission="docker:read">
              <DockerImageComparePage />
            </PermissionGate>
          }
        />

        {/* ── Mirroring / Git Mirroring (v2) ─────────────── */}
        <Route
          path="mirroring/git-mirroring"
          element={
            <PermissionGate permission="pipelines:read">
              <GitMirroring />
            </PermissionGate>
          }
        />

        {/* ── Git Mirroring V2 ──────────────────────────── */}
        <Route
          path="git-mirroring/mirrors"
          element={
            <PermissionGate permission="pipelines:read">
              <GitMirroringMirrors />
            </PermissionGate>
          }
        />
        <Route
          path="git-mirroring/mirrors/:id"
          element={
            <PermissionGate permission="pipelines:read">
              <GitMirroringMirrors />
            </PermissionGate>
          }
        />
        <Route
          path="git-mirroring/repositories"
          element={
            <PermissionGate permission="pipelines:read">
              <GitMirroringRepositories />
            </PermissionGate>
          }
        />
        <Route
          path="git-mirroring/repositories/:id"
          element={
            <PermissionGate permission="pipelines:read">
              <GitMirroringRepositoryDetail />
            </PermissionGate>
          }
        />
        <Route
          path="git-mirroring/providers"
          element={
            <PermissionGate permission="pipelines:read">
              <GitMirroringProviders />
            </PermissionGate>
          }
        />
        <Route
          path="git-mirroring/groups"
          element={
            <PermissionGate permission="pipelines:read">
              <GitMirroringGroups />
            </PermissionGate>
          }
        />
        <Route
          path="git-mirroring/sync-groups"
          element={
            <PermissionGate permission="pipelines:read">
              <GitMirroringSyncGroups />
            </PermissionGate>
          }
        />

        {/* ── Builds / Gold Images ──────────────────────── */}
        <Route
          path="builds/gold-images"
          element={
            <PermissionGate permission="gold_images:read">
              <GoldImagesPage />
            </PermissionGate>
          }
        />

        {/* ── Builds / App Images ───────────────────────── */}
        <Route
          path="builds/app-images"
          element={
            <PermissionGate permission="app_images:read">
              <AppImagesPage />
            </PermissionGate>
          }
        />

        {/* ── Pipelines / Runs ──────────────────────────── */}
        <Route
          path="pipelines/runs"
          element={
            <PermissionGate permission="pipelines:read">
              <PipelinesPage />
            </PermissionGate>
          }
        />

        {/* ── Pipelines / Components ────────────────────── */}
        <Route
          path="pipelines/components"
          element={
            <PermissionGate permission="pipelines:read">
              <GitLabComponentsPage />
            </PermissionGate>
          }
        />

        {/* ── Pipelines / Configurations ────────────────── */}
        <Route
          path="pipelines/configurations"
          element={
            <PermissionGate permission="pipelines:read">
              <PipelineConfigsPage />
            </PermissionGate>
          }
        />

        {/* ── Administration / Users & Roles ────────────── */}
        <Route
          path="admin/users"
          element={
            <PermissionGate permission="users:read">
              <AdminPage />
            </PermissionGate>
          }
        />

        {/* ── Administration / Integrations ─────────────── */}
        <Route
          path="admin/integrations"
          element={
            <PermissionGate permission="integrations:read">
              <SettingsIntegrations />
            </PermissionGate>
          }
        />

        {/* ── Administration / Authentication ───────────── */}
        <Route
          path="admin/authentication"
          element={
            <PermissionGate permission="oidc:read">
              <AuthenticationSettings />
            </PermissionGate>
          }
        />

        {/* ── Administration / Audit Log ────────────────── */}
        <Route
          path="admin/audit"
          element={
            <PermissionGate permission="audit:read">
              <AuditLogPage />
            </PermissionGate>
          }
        />

        {/* ════════════════════════════════════════════════════
            LEGACY REDIRECTS (старые URL → новые URL)
            Сохраняем обратную совместимость для закладок и прямых ссылок.
            После завершения миграции страниц эти редиректы можно удалить.
           ════════════════════════════════════════════════════ */}

        {/* Old Overview → Overview */}
        <Route path="dashboard" element={<Navigate to="/overview" replace />} />

        {/* Old Projects → Mirroring / Repositories */}
        <Route path="projects" element={<Navigate to="/mirroring/repositories" replace />} />
        <Route path="projects/:id" element={<RedirectProjectsId />} />

        {/* Old Mirrors → Mirroring / Repositories */}
        <Route path="mirrors" element={<Navigate to="/mirroring/repositories" replace />} />
        <Route path="mirrors/:id" element={<RedirectMirrorsId />} />

        {/* Old Helm Charts → Mirroring / Helm Charts */}
        <Route path="helm-charts" element={<Navigate to="/mirroring/helm-charts" replace />} />
        <Route path="helm-charts/:id" element={<RedirectHelmChartsId />} />

        {/* Old Docker Images → Mirroring / Docker Images */}
        <Route path="docker-images" element={<Navigate to="/mirroring/docker-images" replace />} />
        <Route path="docker-images/:id" element={<RedirectDockerImagesId />} />
        <Route path="docker-images/compare" element={<Navigate to="/mirroring/docker-images/compare" replace />} />

        {/* Old Gold Images → Builds / Gold Images */}
        <Route path="gold-images" element={<Navigate to="/builds/gold-images" replace />} />

        {/* Old App Images → Builds / App Images */}
        <Route path="app-images" element={<Navigate to="/builds/app-images" replace />} />

        {/* Old Pipelines → Pipelines / Runs */}
        <Route path="pipelines" element={<Navigate to="/pipelines/runs" replace />} />

        {/* Old Admin → Administration / Users */}
        <Route path="admin" element={<Navigate to="/admin/users" replace />} />

        {/* Old Settings → Administration */}
        <Route path="settings/integrations" element={<Navigate to="/admin/integrations" replace />} />
        <Route path="settings/authentication" element={<Navigate to="/admin/authentication" replace />} />
        <Route path="settings/audit-log" element={<Navigate to="/admin/audit" replace />} />
        <Route path="settings/pipelines/components" element={<Navigate to="/pipelines/components" replace />} />
        <Route path="settings" element={<Navigate to="/admin/integrations" replace />} />
      </Route>

      {/* ── Catch-all → Overview ──────────────────────────── */}
      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  );
}
