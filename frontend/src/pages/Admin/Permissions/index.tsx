/**
 * @file Admin/Permissions/index.tsx
 * @description Permissions listing page — shows all available permissions grouped by resource category.
 *              Read-only reference page for administrators.
 * @dependencies antd, ../../../store/api, ../../../types
 * @relatedFiles ./Roles/RoleModal.tsx (shared PERMISSION_GROUPS), ../../../store/api.ts
 */

import { Card, Typography, Flex, Spin } from 'antd';

import type { Permission } from '../../../types';
import { useGetAllPermissionsQuery } from '../../../store/api';

// ── Permission groups (from RoleModal.tsx) ────────────────────────────────────

interface PermissionGroup {
  label: string;
  permissions: string[];
}

const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    label: 'Mirrors',
    permissions: ['mirrors:read', 'mirrors:write', 'mirrors:delete', 'mirrors:sync'],
  },
  {
    label: 'Projects',
    permissions: ['projects:read', 'projects:write', 'projects:delete'],
  },
  {
    label: 'Helm',
    permissions: ['helm:read', 'helm:write', 'helm:delete', 'helm:sync'],
  },
  {
    label: 'Docker',
    permissions: ['docker:read', 'docker:write', 'docker:delete', 'docker:sync'],
  },
  {
    label: 'Gold Images',
    permissions: [
      'gold_images:read',
      'gold_images:write',
      'gold_images:delete',
      'gold_images:build',
    ],
  },
  {
    label: 'App Images',
    permissions: ['app_images:read', 'app_images:write', 'app_images:delete', 'app_images:build'],
  },
  {
    label: 'Users',
    permissions: ['users:read', 'users:write', 'users:delete'],
  },
  {
    label: 'Roles',
    permissions: ['roles:read', 'roles:write', 'roles:delete'],
  },
  {
    label: 'Source Groups',
    permissions: ['source_groups:read', 'source_groups:write', 'source_groups:refresh'],
  },
  {
    label: 'Sync Groups',
    permissions: ['sync_groups:read', 'sync_groups:write', 'sync_groups:delete'],
  },
  {
    label: 'Pipelines',
    permissions: ['pipelines:read', 'pipelines:write', 'pipelines:delete'],
  },
  {
    label: 'Credentials',
    permissions: ['credentials:read', 'credentials:use'],
  },
  {
    label: 'Integrations',
    permissions: ['integrations:read', 'integrations:write'],
  },
  {
    label: 'OIDC',
    permissions: ['oidc:read', 'oidc:write'],
  },
  {
    label: 'Audit',
    permissions: ['audit:read'],
  },
  {
    label: 'Reports',
    permissions: ['reports:read'],
  },
];

// ── Group permissions by resource ─────────────────────────────────────────────

interface PermissionsByGroup {
  label: string;
  items: Permission[];
}

function groupPermissionsByResource(
  allPerms: Permission[],
  groups: PermissionGroup[]
): PermissionsByGroup[] {
  // Build a lookup map of group by permission name
  const groupMap: Record<string, string> = {};
  for (const group of groups) {
    for (const perm of group.permissions) {
      groupMap[perm] = group.label;
    }
  }

  // Group permissions
  const result: Record<string, Permission[]> = {};
  const ungrouped: Permission[] = [];

  for (const perm of allPerms) {
    const group = groupMap[perm.name];
    if (group) {
      if (!result[group]) result[group] = [];
      result[group].push(perm);
    } else {
      ungrouped.push(perm);
    }
  }

  // Build output in order of groups definition
  const output: PermissionsByGroup[] = [];
  for (const group of groups) {
    if (result[group.label]) {
      output.push({ label: group.label, items: result[group.label] });
    }
  }

  // Add ungrouped at the end
  if (ungrouped.length > 0) {
    output.push({ label: 'Other', items: ungrouped });
  }

  return output;
}

// ── Permissions Page ──────────────────────────────────────────────────────────

const PermissionsPage = () => {
  const { data: allPermissions = [], isLoading, isError } = useGetAllPermissionsQuery();

  const grouped = groupPermissionsByResource(allPermissions as Permission[], PERMISSION_GROUPS);

  if (isLoading) {
    return (
      <Flex justify="center" style={{ padding: '40px 0' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  if (isError) {
    return (
      <Card>
        <Typography.Text type="danger">
          Failed to load permissions. Please try again later.
        </Typography.Text>
      </Card>
    );
  }

  return (
    <Flex vertical gap={16}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          Permissions
        </Typography.Title>
        <Typography.Text type="secondary">
          All available permissions in the BigBug platform, grouped by resource category.
        </Typography.Text>
      </div>

      {grouped.map((group) => (
        <Card
          key={group.label}
          size="small"
          title={
            <Flex align="center" gap={8}>
              <Typography.Text strong>{group.label}</Typography.Text>
              <Typography.Text type="secondary">({group.items.length})</Typography.Text>
            </Flex>
          }
        >
          <Flex vertical gap={4}>
            {group.items.map((perm) => (
              <Flex key={perm.id} justify="space-between" align="center">
                <Typography.Text code style={{ fontSize: 13 }}>
                  {perm.name}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12, maxWidth: 300 }}>
                  {perm.description ?? '—'}
                </Typography.Text>
              </Flex>
            ))}
          </Flex>
        </Card>
      ))}

      {grouped.length === 0 && (
        <Card>
          <Typography.Text type="secondary">No permissions found.</Typography.Text>
        </Card>
      )}
    </Flex>
  );
};

export default PermissionsPage;
