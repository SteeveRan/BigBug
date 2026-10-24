/**
 * @file api/trust-stores.ts
 * @description Trust Stores RTK Query endpoints (`/api/trust-stores`, ADR-0037).
 * @dependencies api/base.ts
 */

import type {
  TrustStore,
  TrustStoreCertificatesIn,
  TrustStoreCreate,
  TrustStoreUpdate,
  TrustStoreUsage,
} from '../../types';
import { api } from './base';

export const trustStoresApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getTrustStores: builder.query<TrustStore[], void>({
      query: () => '/trust-stores',
      providesTags: ['TrustStore'],
    }),
    getTrustStore: builder.query<TrustStore, number>({
      query: (id) => `/trust-stores/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'TrustStore', id }],
    }),
    createTrustStore: builder.mutation<TrustStore, TrustStoreCreate>({
      query: (body) => ({ url: '/trust-stores', method: 'POST', body }),
      invalidatesTags: ['TrustStore'],
    }),
    updateTrustStore: builder.mutation<TrustStore, { id: number; data: TrustStoreUpdate }>({
      query: ({ id, data }) => ({ url: `/trust-stores/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'TrustStore', id }, 'TrustStore'],
    }),
    deleteTrustStore: builder.mutation<void, number>({
      query: (id) => ({ url: `/trust-stores/${id}`, method: 'DELETE' }),
      invalidatesTags: ['TrustStore'],
    }),
    getTrustStoreUsage: builder.query<TrustStoreUsage, number>({
      query: (id) => `/trust-stores/${id}/usage`,
    }),
    addTrustStoreCertificates: builder.mutation<
      TrustStore['certificates'],
      { id: number; data: TrustStoreCertificatesIn }
    >({
      query: ({ id, data }) => ({
        url: `/trust-stores/${id}/certificates`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'TrustStore', id }, 'TrustStore'],
    }),
    deleteTrustStoreCertificate: builder.mutation<void, { storeId: number; certificateId: number }>(
      {
        query: ({ storeId, certificateId }) => ({
          url: `/trust-stores/${storeId}/certificates/${certificateId}`,
          method: 'DELETE',
        }),
        invalidatesTags: (_result, _error, { storeId }) => [
          { type: 'TrustStore', id: storeId },
          'TrustStore',
        ],
      }
    ),
  }),
});

export const {
  useGetTrustStoresQuery,
  useGetTrustStoreQuery,
  useCreateTrustStoreMutation,
  useUpdateTrustStoreMutation,
  useDeleteTrustStoreMutation,
  useGetTrustStoreUsageQuery,
  useAddTrustStoreCertificatesMutation,
  useDeleteTrustStoreCertificateMutation,
} = trustStoresApi;
