/**
 * @file api/admin-users.ts
 * @description User management endpoints
 * @dependencies api/base.ts
 */

import { api } from './base';

export const adminUsersApi = api.injectEndpoints({
  endpoints: (builder) => ({
    listUsers: builder.query<unknown[], void>({
      query: () => '/admin/users',
      providesTags: ['User'],
    }),
    createUser: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/admin/users', method: 'POST', body }),
      invalidatesTags: ['User'],
    }),
    updateUser: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/admin/users/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: ['User'],
    }),
    deleteUser: builder.mutation<void, number>({
      query: (id) => ({ url: `/admin/users/${id}`, method: 'DELETE' }),
      invalidatesTags: ['User'],
    }),
  }),
});

export const {
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
} = adminUsersApi;
