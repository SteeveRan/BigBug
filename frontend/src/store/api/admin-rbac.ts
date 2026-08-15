/**
 * @file api/admin-rbac.ts
 * @description RBAC: Permissions, Roles, Role Scopes
 * @dependencies api/base.ts
 */

import type {
  Permission,
  Role,
  RoleScope,
  RoleScopeUpdate,
  ScopeItemRequest,
  User,
  RoleCreate,
  RoleUpdate,
} from '../../types';
import { api } from './base';

export const adminRbacApi = api.injectEndpoints({
  endpoints: (builder) => ({
    // ── Permissions ─────────────────────────────────────────────────

    getAllPermissions: builder.query<Permission[], void>({
      query: () => '/admin/permissions',
      providesTags: ['Permissions'],
    }),

    // ── Roles CRUD ─────────────────────────────────────────────────

    getAllRoles: builder.query<Role[], void>({
      query: () => '/admin/roles',
      providesTags: ['Roles'],
    }),
    getRoleById: builder.query<Role, number>({
      query: (id) => `/admin/roles/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Roles', id }],
    }),
    getRoleUsers: builder.query<User[], number>({
      query: (roleId) => `/admin/roles/${roleId}/users`,
      providesTags: (_result, _error, roleId) => [{ type: 'RoleUsers', id: roleId }],
    }),
    createRole: builder.mutation<Role, RoleCreate>({
      query: (body) => ({ url: '/admin/roles', method: 'POST', body }),
      invalidatesTags: ['Roles'],
    }),
    updateRole: builder.mutation<Role, { id: number; data: RoleUpdate }>({
      query: ({ id, data }) => ({ url: `/admin/roles/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Roles', id }, 'Roles'],
    }),
    deleteRole: builder.mutation<void, number>({
      query: (id) => ({ url: `/admin/roles/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Roles'],
    }),

    // ── Role Scope ─────────────────────────────────────────────────

    getRoleScope: builder.query<
      RoleScope,
      { roleId: number; scopeType: 'source-groups' | 'credentials' | 'sync-groups' | 'providers' }
    >({
      query: ({ roleId, scopeType }) => `/admin/roles/${roleId}/scopes/${scopeType}`,
      providesTags: (_result, _error, { roleId }) => [{ type: 'RoleScope', id: roleId }],
    }),
    addRoleScopeItem: builder.mutation<
      RoleScope,
      {
        roleId: number;
        scopeType: 'source-groups' | 'credentials' | 'sync-groups' | 'providers';
        item: ScopeItemRequest;
      }
    >({
      query: ({ roleId, scopeType, item }) => ({
        url: `/admin/roles/${roleId}/scopes/${scopeType}`,
        method: 'POST',
        body: item,
      }),
      invalidatesTags: (_result, _error, { roleId }) => [{ type: 'RoleScope', id: roleId }],
    }),
    setRoleScope: builder.mutation<
      RoleScope,
      {
        roleId: number;
        scopeType: 'source-groups' | 'credentials' | 'sync-groups' | 'providers';
        data: RoleScopeUpdate;
      }
    >({
      query: ({ roleId, scopeType, data }) => ({
        url: `/admin/roles/${roleId}/scopes/${scopeType}`,
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: (_result, _error, { roleId }) => [{ type: 'RoleScope', id: roleId }],
    }),
    removeRoleScopeItem: builder.mutation<
      void,
      {
        roleId: number;
        scopeType: 'source-groups' | 'credentials' | 'sync-groups' | 'providers';
        itemId: number;
      }
    >({
      query: ({ roleId, scopeType, itemId }) => ({
        url: `/admin/roles/${roleId}/scopes/${scopeType}/${itemId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, { roleId }) => [{ type: 'RoleScope', id: roleId }],
    }),
  }),
});

export const {
  useGetAllPermissionsQuery,
  useGetAllRolesQuery,
  useGetRoleByIdQuery,
  useGetRoleUsersQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
  useGetRoleScopeQuery,
  useAddRoleScopeItemMutation,
  useSetRoleScopeMutation,
  useRemoveRoleScopeItemMutation,
} = adminRbacApi;
