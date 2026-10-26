import { Outlet, useNavigate, useLocation } from 'react-router';
import { Layout as AntLayout, Menu, Button, Typography, Space, theme } from 'antd';
import type { MenuProps } from 'antd';
import {
  TeamOutlined,
  IdcardOutlined,
  KeyOutlined,
  ApiOutlined,
  LockOutlined,
  AuditOutlined,
  ArrowLeftOutlined,
  SunOutlined,
  MoonOutlined,
  DeploymentUnitOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { useThemeMode } from '../../hooks/useThemeMode';
import { usePermissions } from '../../hooks/usePermissions';

const { Header, Content, Sider } = AntLayout;

/**
 * @file AdminLayout/index.tsx
 * @description Отдельный Layout для Admin Panel.
 *              Собственный Sider с меню админки (Users, Roles, Permissions,
 *              Integrations, Authentication, Audit Log).
 *              Кнопка «Back to App» в Header и Theme toggle.
 * @dependencies antd, @ant-design/icons, react-router, ../../hooks/useThemeMode
 * @relatedFiles ../Layout/index.tsx, ../../router/index.tsx
 */

function computeSelectedKey(pathname: string): string[] {
  const normalized = pathname.replace(/\/$/, '') || '/';
  const segments = normalized.split('/').filter(Boolean);
  if (segments.length >= 2) {
    return ['/' + segments.slice(0, 2).join('/')];
  }
  return [normalized];
}

export function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { mode, toggleTheme } = useThemeMode();
  const { hasPermission } = usePermissions();
  const { token } = theme.useToken();

  const isDark = mode === 'dark';
  const selectedKeys = computeSelectedKey(location.pathname);

  // ── Admin menu items ──────────────────────────────────────────
  const adminMenuItems: MenuProps['items'] = [
    { key: '/admin/users', icon: <TeamOutlined />, label: 'Users' },
    { key: '/admin/roles', icon: <IdcardOutlined />, label: 'Roles' },
    { key: '/admin/permissions', icon: <KeyOutlined />, label: 'Permissions' },
    { key: '/admin/teams', icon: <TeamOutlined />, label: 'Teams' },
    { key: '/admin/credentials', icon: <ApiOutlined />, label: 'Credentials' },
    ...(hasPermission('trust_stores:read')
      ? [
          {
            key: '/admin/trust-stores',
            icon: <SafetyCertificateOutlined />,
            label: 'Trust Stores',
          },
        ]
      : []),
    ...(hasPermission('providers_system:write') || hasPermission('providers:read_all')
      ? [{ key: '/admin/providers', icon: <DeploymentUnitOutlined />, label: 'System Providers' }]
      : []),
    { key: '/admin/authentication', icon: <LockOutlined />, label: 'Authentication' },
    { key: '/admin/audit', icon: <AuditOutlined />, label: 'Audit Log' },
    ...(hasPermission('system:config')
      ? [{ key: '/admin/sync-runs', icon: <SyncOutlined />, label: 'Sync Runs' }]
      : []),
  ];

  // Theme-aware colors via canonical tokens (theme.ts / colors.css)
  const headerBg = token.colorBgContainer;
  const headerTextColor = token.colorText;
  const headerSecondaryText = token.colorTextSecondary;

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
              background: 'var(--bigbug-danger-gradient)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            BigBug Admin
          </Typography.Title>
        </div>
        <Menu
          theme={isDark ? 'dark' : 'light'}
          mode="inline"
          selectedKeys={selectedKeys}
          items={adminMenuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header
          style={{
            paddingInline: token.paddingLG,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: headerBg,
          }}
        >
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/overview')}>
            Back to App
          </Button>
          <Space size="middle">
            <Button
              type="text"
              icon={isDark ? <SunOutlined /> : <MoonOutlined />}
              onClick={toggleTheme}
              style={{ color: headerSecondaryText }}
              title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            />
            <Typography.Title level={4} style={{ margin: 0, color: headerTextColor }}>
              Admin Panel
            </Typography.Title>
          </Space>
        </Header>
        <Content style={{ padding: 24 }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}

export default AdminLayout;
