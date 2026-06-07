import { Routes, Route, Navigate } from 'react-router';
import { useAppSelector } from '../store';
import { Layout } from '../components/Layout';
import { ProtectedRoute } from './ProtectedRoute';
import { PermissionGate } from '../components/PermissionGate';
import { LoginPage } from '../pages/Login';
import { SsoCallbackPage } from '../pages/SsoCallback';
import { DashboardPage } from '../pages/Dashboard';
import { ProjectsPage } from '../pages/Projects';
import { ProjectDetailPage } from '../pages/Projects/ProjectDetail';
import { MirrorsPage } from '../pages/Mirrors';
import { MirrorDetailPage } from '../pages/Mirrors/MirrorDetail';
import { GoldImagesPage } from '../pages/GoldImages';
import { AppImagesPage } from '../pages/AppImages';
import { HelmChartsPage } from '../pages/HelmCharts';
import { HelmChartDetailPage } from '../pages/HelmCharts/HelmChartDetail';
import { DockerImagesPage } from '../pages/DockerImages';
import { DockerImageDetailPage } from '../pages/DockerImages/DockerImageDetail';
import { AdminPage } from '../pages/Admin';
import SettingsIntegrations from '../pages/Settings/Integrations';
import { AuthenticationSettings } from '../pages/Settings/Authentication';
import AuditLogPage from '../pages/Settings/AuditLog';
import { PipelinesPage } from '../pages/Pipelines';
import { GitLabComponentsPage } from '../pages/Settings/Pipelines';

export function AppRouter() {
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated);

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route path="/sso/callback" element={<SsoCallbackPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:id" element={<ProjectDetailPage />} />
        <Route path="mirrors" element={<MirrorsPage />} />
        <Route path="mirrors/:id" element={<MirrorDetailPage />} />
        <Route path="gold-images" element={<GoldImagesPage />} />
        <Route path="app-images" element={<AppImagesPage />} />
        <Route path="helm-charts" element={<HelmChartsPage />} />
        <Route path="helm-charts/:id" element={<HelmChartDetailPage />} />
        <Route path="docker-images" element={<DockerImagesPage />} />
        <Route path="docker-images/:id" element={<DockerImageDetailPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route
          path="settings/integrations"
          element={
            <PermissionGate permission="integrations:manage">
              <SettingsIntegrations />
            </PermissionGate>
          }
        />
        <Route
          path="settings/authentication"
          element={
            <PermissionGate permission="integrations:manage">
              <AuthenticationSettings />
            </PermissionGate>
          }
        />
        <Route path="pipelines" element={<PipelinesPage />} />
        <Route
          path="settings/pipelines/components"
          element={
            <PermissionGate permission="pipelines:read">
              <GitLabComponentsPage />
            </PermissionGate>
          }
        />
        <Route
          path="settings/audit-log"
          element={
            <PermissionGate permission="users:read">
              <AuditLogPage />
            </PermissionGate>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
