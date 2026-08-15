/**
 * @file Profile/index.tsx
 * @description Личный кабинет пользователя (`/profile`): read-only профиль,
 *              «My teams» и «My providers». Заменяет `/settings/teams`.
 * @dependencies antd, RTK Query, Redux (authSlice), PermissionGate
 * @relatedFiles ./MyTeamsCard.tsx, ./MyProvidersCard.tsx, ./splitMyProviders.ts
 */

import { useMemo } from 'react';
import { Alert, Avatar, Badge, Card, Descriptions, Empty, Flex, Spin, Tag, Typography } from 'antd';
import { UserOutlined } from '@ant-design/icons';
import { useAppSelector } from '../../store';
import { useGetMeQuery, useGetTeamsQuery } from '../../store/api';
import { PermissionGate } from '../../components/PermissionGate';
import { MyTeamsCard } from './MyTeamsCard';
import { MyProvidersCard } from './MyProvidersCard';

const roleColorMap: Record<string, string> = {
  admin: 'red',
  operator: 'blue',
  viewer: 'green',
};

export function ProfilePage() {
  const authUser = useAppSelector((state) => state.auth.user);
  // Лёгкая догрузка `/auth/me` для актуализации full_name/ролей после смены админом.
  const { data: me, isLoading: meLoading, isError: meError } = useGetMeQuery();
  const { data: teams = [], isLoading: teamsLoading, isError: teamsError } = useGetTeamsQuery();

  const user = me ?? authUser;

  // Только команды, где пользователь реально член (для админа, который видит все команды).
  const myTeams = useMemo(() => teams.filter((t) => t.my_role !== null), [teams]);

  // Множество ID команд членства — для деления провайдеров на owned/shared.
  const myTeamIds = useMemo(() => new Set(myTeams.map((t) => t.id)), [myTeams]);

  const fullName = user?.full_name ?? user?.username ?? '—';
  const roles = user?.roles ?? [];

  return (
    <Flex vertical gap={16}>
      <Flex vertical gap={4}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          My Profile
        </Typography.Title>
        <Typography.Text type="secondary">
          Your personal account. Profile data is managed via SSO / by administrators.
        </Typography.Text>
      </Flex>

      {/* ── Card 1: Profile ─────────────────────────────────── */}
      <Card title="Profile">
        {meLoading && !user ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
            <Spin size="large" />
          </div>
        ) : meError && !user ? (
          <Alert title="Failed to load profile" type="error" showIcon />
        ) : (
          <Flex gap={24} wrap>
            <Flex vertical align="center" gap={8}>
              <Badge status={user?.is_active ? 'success' : 'default'}>
                <Avatar size={64} icon={<UserOutlined />}>
                  {(user?.username ?? '?')[0].toUpperCase()}
                </Avatar>
              </Badge>
              <Typography.Title level={5} style={{ margin: 0 }}>
                {fullName}
              </Typography.Title>
              {roles.length > 0 && (
                <Flex gap={4} wrap justify="center">
                  {roles.map((role) => (
                    <Tag key={role} color={roleColorMap[role] ?? 'default'}>
                      {role}
                    </Tag>
                  ))}
                </Flex>
              )}
            </Flex>

            <Descriptions column={1} layout="vertical" style={{ flex: 1, minWidth: 240 }}>
              <Descriptions.Item label="Username">
                <Typography.Text code>{user?.username ?? '—'}</Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="Email">
                <Typography.Text>{user?.email ?? '—'}</Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="Full name">
                <Typography.Text>{user?.full_name ?? '—'}</Typography.Text>
              </Descriptions.Item>
            </Descriptions>
          </Flex>
        )}
      </Card>

      {/* ── Card 2: My teams ────────────────────────────────── */}
      <PermissionGate permission="teams:read" fallback={<Empty description="No teams access" />}>
        <MyTeamsCard teams={myTeams} isLoading={teamsLoading} isError={teamsError} />
      </PermissionGate>

      {/* ── Card 3: My providers ────────────────────────────── */}
      <PermissionGate
        permission="providers:read"
        fallback={<Empty description="No providers access" />}
      >
        <MyProvidersCard userId={user?.id} myTeamIds={myTeamIds} />
      </PermissionGate>
    </Flex>
  );
}

export default ProfilePage;
