/**
 * @file usePermissions.ts
 * @description Hook for checking RBAC permissions from the Redux auth state.
 *              Permissions are stored as a string[] (e.g. ["mirrors:read", "helm:write"]).
 *
 * @dependencies ../store (useAppSelector), ../store/authSlice (selectUserPermissions)
 * @relatedFiles ../components/PermissionGate.tsx
 */

import { useCallback } from 'react'
import { useAppSelector } from '../store'
import { selectUserPermissions } from '../store/authSlice'

/**
 * usePermissions hook — checks user permissions from Redux store.
 *
 * Reads permissions from authSlice state (populated from JWT or API).
 *
 * Usage:
 *   const { hasPermission, hasAnyPermission, hasAllPermissions, permissions } = usePermissions();
 *
 *   if (hasPermission("mirrors:read")) { ... }
 *   if (hasAnyPermission(["helm:write", "helm:delete"])) { ... }
 *   if (hasAllPermissions(["mirrors:read", "helm:read"])) { ... }
 */
export function usePermissions() {
  const permissions = useAppSelector(selectUserPermissions)

  /** Check if the user has a specific permission */
  const hasPermission = useCallback(
    (permission: string): boolean => {
      return permissions.includes(permission)
    },
    [permissions]
  )

  /** Check if the user has at least one of the required permissions (OR logic) */
  const hasAnyPermission = useCallback(
    (requiredPermissions: string[]): boolean => {
      return requiredPermissions.some((p) => permissions.includes(p))
    },
    [permissions]
  )

  /** Check if the user has all of the required permissions (AND logic) */
  const hasAllPermissions = useCallback(
    (requiredPermissions: string[]): boolean => {
      return requiredPermissions.every((p) => permissions.includes(p))
    },
    [permissions]
  )

  return {
    /** Current permissions string[] (e.g. ["mirrors:read", "helm:write"]) */
    permissions,
    /** Check a single permission */
    hasPermission,
    /** Check if user has ANY of the given permissions (OR) */
    hasAnyPermission,
    /** Check if user has ALL of the given permissions (AND) */
    hasAllPermissions,
  }
}
