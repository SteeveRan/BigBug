import { Routes, Route, Navigate } from 'react-router'
import { useAppSelector } from '../store'
import { Layout } from '../components/Layout'
import { ProtectedRoute } from './ProtectedRoute'
import { LoginPage } from '../pages/Login'
import { SsoCallbackPage } from '../pages/SsoCallback'
import { DashboardPage } from '../pages/Dashboard'
import { ProjectsPage } from '../pages/Projects'
import { ProjectDetailPage } from '../pages/Projects/ProjectDetail'
import { MirrorsPage } from '../pages/Mirrors'
import { MirrorDetailPage } from '../pages/Mirrors/MirrorDetail'
import { GoldImagesPage } from '../pages/GoldImages'
import { AppImagesPage } from '../pages/AppImages'
import { AdminPage } from '../pages/Admin'

export function AppRouter() {
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated)

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
        <Route path="admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
