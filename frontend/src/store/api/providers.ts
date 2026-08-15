/**
 * @file api/providers.ts
 * @description Unified Providers V3 RTK Query endpoints (`/api/providers`).
 * @dependencies api/base.ts
 */

import type {
  ProviderActionOut,
  ProviderCreate,
  ProviderTestResult,
  ProviderTypeSpec,
  ProviderUpdate,
  ProviderUsage,
  ResourceProvider,
} from '../../types';
import { api } from './base';

export interface ProviderListParams {
  domain?: string;
  subtype?: string;
  category?: string;
  direction?: string;
  owner?: string;
  page?: number;
  page_size?: number;
}

export const providersApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getProviderTypes: builder.query<ProviderTypeSpec[], void>({
      query: () => '/providers/types',
      providesTags: ['ProviderType'],
    }),
    getProviders: builder.query<ResourceProvider[], ProviderListParams | undefined>({
      query: (params) => ({ url: '/providers', params: params ?? undefined }),
      providesTags: ['Provider'],
    }),
    getProvider: builder.query<ResourceProvider, number>({
      query: (id) => `/providers/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Provider', id }],
    }),
    createProvider: builder.mutation<ResourceProvider, ProviderCreate>({
      query: (body) => ({ url: '/providers', method: 'POST', body }),
      invalidatesTags: ['Provider'],
    }),
    updateProvider: builder.mutation<ResourceProvider, { id: number; data: ProviderUpdate }>({
      query: ({ id, data }) => ({ url: `/providers/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Provider', id }, 'Provider'],
    }),
    deleteProvider: builder.mutation<void, number>({
      query: (id) => ({ url: `/providers/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Provider'],
    }),
    testProvider: builder.mutation<ProviderTestResult, number>({
      query: (id) => ({ url: `/providers/${id}/test`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Provider', id }],
    }),
    runProviderAction: builder.mutation<
      ProviderActionOut,
      { id: number; action: string; params?: Record<string, unknown> }
    >({
      query: ({ id, action, params }) => ({
        url: `/providers/${id}/actions/${action}`,
        method: 'POST',
        body: { params: params ?? {} },
      }),
    }),
    getProviderUsage: builder.query<ProviderUsage, number>({
      query: (id) => `/providers/${id}/usage`,
    }),
    shareProvider: builder.mutation<ResourceProvider, { id: number; team_id: number }>({
      query: ({ id, team_id }) => ({
        url: `/providers/${id}/share`,
        method: 'POST',
        body: { team_id },
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Provider', id }, 'Provider'],
    }),
    unshareProvider: builder.mutation<ResourceProvider, number>({
      query: (id) => ({ url: `/providers/${id}/unshare`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Provider', id }, 'Provider'],
    }),
  }),
});

export const {
  useGetProviderTypesQuery,
  useGetProvidersQuery,
  useGetProviderQuery,
  useCreateProviderMutation,
  useUpdateProviderMutation,
  useDeleteProviderMutation,
  useTestProviderMutation,
  useRunProviderActionMutation,
  useGetProviderUsageQuery,
  useShareProviderMutation,
  useUnshareProviderMutation,
} = providersApi;
