/**
 * @file api/trust-stores.ts
 * @description Trust Store read endpoints (ADR-0037). Only the list query lives
 *              here for now — the full admin CRUD belongs to the Trust Stores
 *              admin page (issue #91).
 * @dependencies api/base.ts
 */

import { api } from './base';

export interface TrustStore {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export const trustStoresApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getTrustStores: builder.query<TrustStore[], void>({
      query: () => '/trust-stores',
      providesTags: ['TrustStore'],
    }),
  }),
});

export const { useGetTrustStoresQuery } = trustStoresApi;
