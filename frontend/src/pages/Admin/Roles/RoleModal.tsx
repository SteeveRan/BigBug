/**
 * @file Admin/Roles/RoleModal.tsx
 * @description Modal for creating/editing a role with permission checkboxes grouped by resource.
 *              Uses RTK Query mutations and invalidates the Roles cache on success.
 * @dependencies antd, @ant-design/icons, ../../../store/api, ../../../types
 * @relatedFiles ./index.tsx, ../../../store/api.ts, ../../../types/index.ts
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Modal, Form, Input, Button, Card, Checkbox, Typography, Flex, App } from 'antd';

import type { Role, RoleCreate, Permission } from '../../../types';
import {
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useGetAllPermissionsQuery,
} from '../../../store/api';

interface RoleModalProps {
  open: boolean;
  role?: Role;
  onClose: () => void;
}

interface FormValues {
  name: string;
  description: string;
}

// ── Permission groups ─────────────────────────────────────────────────────────

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

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Derive a human-readable label from a permission string like "mirrors:read" */
function permissionLabel(perm: string): string {
  const [resource, action] = perm.split(':');
  if (!action) return perm;
  return `${action} → ${resource}`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function RoleModal({ open, role, onClose }: RoleModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const isEdit = !!role;

  const { data: allPermissions = [] } = useGetAllPermissionsQuery();
  const [createRole, { isLoading: isCreating }] = useCreateRoleMutation();
  const [updateRole, { isLoading: isUpdating }] = useUpdateRoleMutation();
  const isLoading = isCreating || isUpdating;

  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  // ── All known permission names from the backend ────────────────────────────
  const allPermissionNames = useMemo(() => {
    return allPermissions.map((p: Permission) => p.name);
  }, [allPermissions]);

  // Build a set for O(1) lookups
  const permissionSet = useMemo(() => new Set(allPermissionNames), [allPermissionNames]);

  // ── Initialize form when modal opens ───────────────────────────────────────
  useEffect(() => {
    if (open) {
      if (role) {
        form.setFieldsValue({
          name: role.name,
          description: role.description ?? '',
        });
        setSelectedPermissions(role.permissions.map((p) => p.name));
      } else {
        form.resetFields();
        setSelectedPermissions([]);
      }
    }
  }, [open, role, form]);

  // ── Group selection helpers ───────────────────────────────────────────────
  const isGroupAllSelected = useCallback(
    (group: PermissionGroup): boolean => {
      const available = group.permissions.filter((p) => permissionSet.has(p));
      if (available.length === 0) return false;
      return available.every((p) => selectedPermissions.includes(p));
    },
    [selectedPermissions, permissionSet]
  );

  const isGroupSomeSelected = useCallback(
    (group: PermissionGroup): boolean => {
      return group.permissions.some((p) => selectedPermissions.includes(p));
    },
    [selectedPermissions]
  );

  const handleToggleGroup = useCallback(
    (group: PermissionGroup, select: boolean) => {
      setSelectedPermissions((prev) => {
        if (select) {
          const toAdd = group.permissions.filter((p) => permissionSet.has(p) && !prev.includes(p));
          return [...prev, ...toAdd];
        }
        return prev.filter((p) => !group.permissions.includes(p));
      });
    },
    [permissionSet]
  );

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async (values: FormValues) => {
    try {
      if (isEdit && role) {
        await updateRole({
          id: role.id,
          data: {
            name: values.name.trim() !== role.name ? values.name.trim() : undefined,
            description:
              (values.description?.trim() ?? '') !== (role.description ?? '')
                ? values.description?.trim() || null
                : undefined,
            permission_names: selectedPermissions,
          },
        }).unwrap();
        message.success(`Role "${values.name.trim()}" updated successfully`);
      } else {
        const data: RoleCreate = {
          name: values.name.trim(),
          description: values.description?.trim() || undefined,
          permission_names: selectedPermissions,
        };
        await createRole(data).unwrap();
        message.success(`Role "${data.name}" created successfully`);
      }
      onClose();
    } catch {
      // Error handled by RTK Query
    }
  };

  return (
    <Modal
      title={isEdit ? `Edit Role: ${role?.name}` : 'Create Role'}
      open={open}
      onCancel={onClose}
      width={720}
      footer={[
        <Button key="cancel" onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>,
        <Button key="save" type="primary" loading={isLoading} onClick={() => form.submit()}>
          {isEdit ? 'Save' : 'Create'}
        </Button>,
      ]}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        {/* Name */}
        <Form.Item
          name="name"
          label="Name"
          rules={[
            { required: true, message: 'Role name is required' },
            { min: 1, message: 'Name must be at least 1 character' },
          ]}
        >
          <Input placeholder="e.g. dev_lead" disabled={isLoading} />
        </Form.Item>

        {/* Description */}
        <Form.Item name="description" label="Description">
          <Input placeholder="Optional description" disabled={isLoading} />
        </Form.Item>
      </Form>

      {/* Permissions */}
      <Flex vertical gap={12}>
        <Typography.Text strong>Permissions</Typography.Text>
        {PERMISSION_GROUPS.map((group) => {
          // Only show groups that have at least one known permission
          const availablePerms = group.permissions.filter((p) => permissionSet.has(p));
          if (availablePerms.length === 0) return null;

          return (
            <Card
              key={group.label}
              size="small"
              title={<Typography.Text strong>{group.label}</Typography.Text>}
              extra={
                <Flex gap={4}>
                  <Button
                    size="small"
                    type="link"
                    onClick={() => handleToggleGroup(group, true)}
                    disabled={isLoading || isGroupAllSelected(group)}
                  >
                    Select All
                  </Button>
                  <Button
                    size="small"
                    type="link"
                    onClick={() => handleToggleGroup(group, false)}
                    disabled={isLoading || !isGroupSomeSelected(group)}
                  >
                    Deselect All
                  </Button>
                </Flex>
              }
            >
              <Checkbox.Group
                style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}
                options={availablePerms.map((perm) => ({
                  label: permissionLabel(perm),
                  value: perm,
                }))}
                value={selectedPermissions.filter((p) => group.permissions.includes(p))}
                onChange={(checkedValues: string[]) => {
                  const otherPerms = selectedPermissions.filter(
                    (p) => !group.permissions.includes(p)
                  );
                  setSelectedPermissions([...otherPerms, ...checkedValues]);
                }}
              />
            </Card>
          );
        })}
      </Flex>
    </Modal>
  );
}

export default RoleModal;
