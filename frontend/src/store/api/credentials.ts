/**
 * @file api/credentials.ts
 * @description Credentials RTK Query endpoints (`/api/credentials`).
 * @dependencies api/base.ts
 */

import type { CredentialCreate, CredentialDetail, CredentialUpdate } from '../../types';
import { api } from './base';

export const credentialsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getCredentials: builder.query<CredentialDetail[], void>({
      query: () => '/credentials',
      providesTags: ['Credential'],
    }),
    createCredential: builder.mutation<CredentialDetail, CredentialCreate>({
      query: (body) => ({ url: '/credentials', method: 'POST', body }),
      invalidatesTags: ['Credential'],
    }),
    updateCredential: builder.mutation<CredentialDetail, { id: number; data: CredentialUpdate }>({
      query: ({ id, data }) => ({ url: `/credentials/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Credential', id }, 'Credential'],
    }),
    deleteCredential: builder.mutation<void, number>({
      query: (id) => ({ url: `/credentials/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Credential'],
    }),
    testCredential: builder.mutation<CredentialDetail, number>({
      query: (id) => ({ url: `/credentials/${id}/test`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Credential', id }],
    }),
  }),
});

export const {
  useGetCredentialsQuery,
  useCreateCredentialMutation,
  useUpdateCredentialMutation,
  useDeleteCredentialMutation,
  useTestCredentialMutation,
} = credentialsApi;
