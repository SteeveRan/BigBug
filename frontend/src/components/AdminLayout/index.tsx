import { Outlet, useNavigate, useLocation } from 'react-router';
import { Layout as AntLayout, Menu, Button, Typography, Space } from 'antd';
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
} from '@ant-design/icons';
import { useThemeMode } from '../../hooks/useThemeMode';

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

  const isDark = mode === 'dark';
  const selectedKeys = computeSelectedKey(location.pathname);

  // ── Admin menu items ──────────────────────────────────────────
  const adminMenuItems: MenuProps['items'] = [
    { key: '/admin/users', icon: <TeamOutlined />, label: 'Users' },
    { key: '/admin/roles', icon: <IdcardOutlined />, label: 'Roles' },
    { key: '/admin/permissions', icon: <KeyOutlined />, label: 'Permissions' },
    { key: '/admin/integrations', icon: <ApiOutlined />, label: 'Integrations' },
    { key: '/admin/authentication', icon: <LockOutlined />, label: 'Authentication' },
    { key: '/admin/audit', icon: <AuditOutlined />, label: 'Audit Log' },
  ];

  // Theme-aware colors
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
              background: 'linear-gradient(135deg, #DC2626 0%, #EF4444 50%, #F87171 100%)',
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
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: headerBg,
          }}
        >
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/overview')}
          >
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
