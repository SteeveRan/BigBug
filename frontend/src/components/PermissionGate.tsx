/**
 * @file PermissionGate.tsx
 * @description Conditionally renders children based on RBAC permissions.
 *              Uses the usePermissions hook to check against the Redux auth state.
 *
 * @dependencies ../hooks/usePermissions
 * @relatedFiles ../hooks/usePermissions.ts
 */

import type { ReactNode, ReactElement } from 'react';
import { usePermissions } from '../hooks/usePermissions';

interface PermissionGateProps {
  /** Single permission required (e.g. "mirrors:write") */
  permission?: string;

  /** Render children if user has ANY of these permissions (OR logic) */
  anyOf?: string[];

  /** Render children if user has ALL of these permissions (AND logic) */
  allOf?: string[];

  /** Content to render if the permission check fails (default: null) */
  fallback?: ReactNode;

  /** Content to render if the permission check passes */
  children: ReactNode;
}

/**
 * PermissionGate — conditionally renders children based on permissions.
 *
 * Usage:
 *   // Show button only for users with mirrors:write permission
 *   <PermissionGate permission="mirrors:write">
 *     <Button>Sync</Button>
 *   </PermissionGate>
 *
 *   // Show with fallback UI
 *   <PermissionGate permission="roles:delete" fallback={<span>No access</span>}>
 *     <DeleteButton />
 *   </PermissionGate>
 *
 *   // Require any of multiple permissions (OR)
 *   <PermissionGate anyOf={["helm:write", "helm:delete"]}>
 *     <HelmActions />
 *   </PermissionGate>
 *
 *   // Require all of multiple permissions (AND)
 *   <PermissionGate allOf={["mirrors:read", "mirrors:write"]}>
 *     <MirrorManager />
 *   </PermissionGate>
 */
export function PermissionGate({
  permission,
  anyOf,
  allOf,
  fallback = null,
  children,
}: PermissionGateProps): ReactElement | null {
  const { hasPermission, hasAnyPermission, hasAllPermissions } = usePermissions();

  let hasAccess = true;

  if (permission) {
    hasAccess = hasPermission(permission);
  } else if (anyOf) {
    hasAccess = hasAnyPermission(anyOf);
  } else if (allOf) {
    hasAccess = hasAllPermissions(allOf);
  }

  if (!hasAccess) {
    return fallback !== null ? <>{fallback}</> : null;
  }

  return <>{children}</>;
}

export default PermissionGate;
