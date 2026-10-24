/**
 * @file api/oidc-providers.ts
 * @description Admin CRUD endpoints for OIDC providers (multi-provider SSO).
 * @dependencies api/base.ts
 */

import type { OIDCProvider, OIDCProviderCreate, OIDCProviderUpdate } from '../../types';
import { api } from './base';

export const oidcProvidersApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getOidcProviders: builder.query<OIDCProvider[], void>({
      query: () => '/auth/admin/oidc-providers',
      providesTags: ['OIDCConfig'],
    }),
    createOidcProvider: builder.mutation<OIDCProvider, OIDCProviderCreate>({
      query: (data) => ({ url: '/auth/admin/oidc-providers', method: 'POST', body: data }),
      invalidatesTags: ['OIDCConfig'],
    }),
    updateOidcProvider: builder.mutation<OIDCProvider, { id: number; data: OIDCProviderUpdate }>({
      query: ({ id, data }) => ({
        url: `/auth/admin/oidc-providers/${id}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: ['OIDCConfig'],
    }),
    deleteOidcProvider: builder.mutation<void, number>({
      query: (id) => ({ url: `/auth/admin/oidc-providers/${id}`, method: 'DELETE' }),
      invalidatesTags: ['OIDCConfig'],
    }),
  }),
});

export const {
  useGetOidcProvidersQuery,
  useCreateOidcProviderMutation,
  useUpdateOidcProviderMutation,
  useDeleteOidcProviderMutation,
} = oidcProvidersApi;
