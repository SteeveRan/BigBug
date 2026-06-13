import { Outlet, useNavigate, useLocation } from 'react-router';
import { Layout as AntLayout, Menu, Dropdown, Avatar, Tag, Typography, Button, Space } from 'antd';
import type { MenuProps } from 'antd';
import {
  DashboardOutlined,
  SyncOutlined,
  GithubOutlined,
  CodeOutlined,
  ContainerOutlined,
  ForkOutlined,
  BuildOutlined,
  GoldOutlined,
  AppstoreOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  SettingOutlined,
  BlockOutlined,
  SafetyOutlined,
  TeamOutlined,
  ApiOutlined,
  LockOutlined,
  AuditOutlined,
  LogoutOutlined,
  UserOutlined,
  SunOutlined,
  MoonOutlined,
  IdcardOutlined,
} from '@ant-design/icons';
import { useAppDispatch, useAppSelector } from '../../store';
import { logout } from '../../store/authSlice';
import { useThemeMode } from '../../contexts/ThemeContext';

const { Header, Content, Sider } = AntLayout;

/**
 * @file Layout/index.tsx
 * @description Главный каркас приложения BigBug.
 *              Sider с новым многоуровневым меню (группы: Mirroring, Builds, Pipelines, Administration).
 *              Header с градиентным логотипом, ThemeToggle и пользовательским Dropdown.
 *              Поддерживает светлую/тёмную тему через useThemeMode().
 * @dependencies antd, @ant-design/icons, react-router, @reduxjs/toolkit, ../../contexts/ThemeContext
 * @relatedFiles ../../store/index.ts, ../../store/authSlice.ts, ../../contexts/ThemeContext.tsx, ../../theme.ts
 */

/**
 * Compute the selected menu key from the current URL path.
 * For detail pages (/mirroring/repositories/123), returns the parent prefix (/mirroring/repositories).
 */
function computeSelectedKey(pathname: string): string[] {
  // Remove trailing slash
  const normalized = pathname.replace(/\/$/, '') || '/';

  // Top-level exact matches
  if (normalized === '/overview') return ['/overview'];

  // For nested paths — match the first two segments as the parent menu key
  // e.g. /mirroring/repositories/123 → /mirroring/repositories
  // e.g. /git-mirroring/mirrors/123 → /git-mirroring/mirrors
  // e.g. /admin/users → /admin/users
  const segments = normalized.split('/').filter(Boolean);
  if (segments.length >= 2) {
    const parentKey = '/' + segments.slice(0, 2).join('/');
    return [parentKey];
  }

  return [normalized];
}

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useAppDispatch();
  const user = useAppSelector((state) => state.auth.user);
  const { mode, toggleTheme } = useThemeMode();

  const isDark = mode === 'dark';

  const handleLogout = () => {
    dispatch(logout());
    navigate('/login');
  };

  const selectedKeys = computeSelectedKey(location.pathname);

  // ── Menu items ─────────────────────────────────────────────
  const menuItems: MenuProps['items'] = [
    {
      key: '/overview',
      icon: <DashboardOutlined />,
      label: 'Overview',
    },
    {
      key: 'group-mirroring',
      label: (
        <span>
          <SyncOutlined style={{ marginRight: 8 }} />
          Mirroring
        </span>
      ),
      type: 'group',
      children: [
        { key: '/mirroring/repositories', icon: <GithubOutlined />, label: 'Repositories' },
        { key: '/mirroring/helm-charts', icon: <CodeOutlined />, label: 'Helm Charts' },
        { key: '/mirroring/docker-images', icon: <ContainerOutlined />, label: 'Docker Images' },
      ],
    },
    {
      key: 'group-builds',
      label: (
        <span>
          <BuildOutlined style={{ marginRight: 8 }} />
          Builds
        </span>
      ),
      type: 'group',
      children: [
        { key: '/builds/gold-images', icon: <GoldOutlined />, label: 'Gold Images' },
        { key: '/builds/app-images', icon: <AppstoreOutlined />, label: 'App Images' },
      ],
    },
    {
      key: 'group-pipelines',
      label: (
        <span>
          <ThunderboltOutlined style={{ marginRight: 8 }} />
          Pipelines
        </span>
      ),
      type: 'group',
      children: [
        { key: '/pipelines/runs', icon: <PlayCircleOutlined />, label: 'Pipeline Runs' },
        { key: '/pipelines/configurations', icon: <SettingOutlined />, label: 'Configurations' },
        { key: '/pipelines/components', icon: <BlockOutlined />, label: 'GitLab Components' },
      ],
    },
    {
      key: 'group-administration',
      label: (
        <span>
          <SafetyOutlined style={{ marginRight: 8 }} />
          Administration
        </span>
      ),
      type: 'group',
      children: [
        { key: '/admin/users', icon: <TeamOutlined />, label: 'Users & Roles' },
        { key: '/admin/roles', icon: <IdcardOutlined />, label: 'Roles' },
        { key: '/admin/integrations', icon: <ApiOutlined />, label: 'Integrations' },
        { key: '/admin/authentication', icon: <LockOutlined />, label: 'Authentication' },
        { key: '/admin/audit', icon: <AuditOutlined />, label: 'Audit Log' },
      ],
    },
    {
      key: 'group-git-mirroring',
      label: (
        <span>
          <ForkOutlined style={{ marginRight: 8 }} />
          Git Mirroring
        </span>
      ),
      type: 'group',
      children: [
        { key: '/git-mirroring/mirrors', icon: <SyncOutlined />, label: 'Mirrors' },
        { key: '/git-mirroring/repositories', icon: <GithubOutlined />, label: 'Repositories' },
        { key: '/git-mirroring/providers', icon: <ApiOutlined />, label: 'Source Providers' },
        { key: '/git-mirroring/groups', icon: <AppstoreOutlined />, label: 'Source Groups' },
        { key: '/git-mirroring/sync-groups', icon: <BlockOutlined />, label: 'Sync Groups' },
      ],
    },
  ];

  // ── User dropdown ──────────────────────────────────────────
  const userMenuItems: MenuProps['items'] = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Sign Out',
      onClick: handleLogout,
    },
  ];

  const roleColorMap: Record<string, string> = {
    admin: 'red',
    operator: 'blue',
    viewer: 'green',
  };

  const userRole = user?.roles[0] ?? 'viewer';

  // Theme-aware colors matching theme.ts tokens
  const headerBg = isDark ? '#1A1A2E' : '#FFFFFF';
  const headerTextColor = isDark ? '#F1F0FB' : '#1A1A2E';
  const headerSecondaryText = isDark ? '#A0A0B8' : '#5C5C78';

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider collapsible breakpoint="lg">
        <div
          style={{
            height: 48,
            margin: 16,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography.Title
            level={4}
            style={{
              margin: 0,
              background: 'linear-gradient(135deg, #7C3AED 0%, #A78BFA 50%, #C4B5FD 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            BigBug
          </Typography.Title>
        </div>
        <Menu
          theme={isDark ? 'dark' : 'light'}
          mode="inline"
          selectedKeys={selectedKeys}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header
          style={{
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: headerBg,
          }}
        >
          <Space>
            <Typography.Title level={4} style={{ margin: 0, color: headerTextColor }}>
              BigBug
            </Typography.Title>
          </Space>
          <Space size="middle">
            <Button
              type="text"
              icon={isDark ? <SunOutlined /> : <MoonOutlined />}
              onClick={toggleTheme}
              style={{ color: headerSecondaryText }}
              title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            />
            {user && (
              <Dropdown menu={{ items: userMenuItems }} trigger={['click']}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                  }}
                >
                  <Avatar size="small" icon={<UserOutlined />}>
                    {user.username[0].toUpperCase()}
                  </Avatar>
                  <span style={{ color: headerTextColor }}>{user.username}</span>
                  <Tag color={roleColorMap[userRole] ?? 'default'}>{userRole}</Tag>
                </div>
              </Dropdown>
            )}
          </Space>
        </Header>
        <Content style={{ padding: 24 }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
