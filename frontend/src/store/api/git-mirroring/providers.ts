/**
 * @file api/git-mirroring/providers.ts
 * @description Source Providers CRUD endpoints
 * @dependencies api/base.ts
 */

import type { SourceProvider, SourceProviderCreate, SourceProviderUpdate } from '../../../types';
import { api } from '../base';

export const sourceProvidersApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getSourceProviders: builder.query<SourceProvider[], void>({
      query: () => '/mirroring/providers',
      providesTags: ['SourceProvider'],
    }),
    createSourceProvider: builder.mutation<SourceProvider, SourceProviderCreate>({
      query: (body) => ({ url: '/mirroring/providers', method: 'POST', body }),
      invalidatesTags: ['SourceProvider'],
    }),
    updateSourceProvider: builder.mutation<
      SourceProvider,
      { id: number; data: SourceProviderUpdate }
    >({
      query: ({ id, data }) => ({
        url: `/mirroring/providers/${id}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: 'SourceProvider', id },
        'SourceProvider',
      ],
    }),
    deleteSourceProvider: builder.mutation<void, number>({
      query: (id) => ({ url: `/mirroring/providers/${id}`, method: 'DELETE' }),
      invalidatesTags: ['SourceProvider'],
    }),
  }),
});

export const {
  useGetSourceProvidersQuery,
  useCreateSourceProviderMutation,
  useUpdateSourceProviderMutation,
  useDeleteSourceProviderMutation,
} = sourceProvidersApi;
