/**
 * @file api/auth.ts
 * @description Auth endpoints: login, SSO, user info
 * @dependencies api/base.ts
 */

import type { UserPermissions } from '../../types';
import { api } from './base';

export const authApi = api.injectEndpoints({
  endpoints: (builder) => ({
    login: builder.mutation<
      { access_token: string; refresh_token: string; token_type: string },
      { username: string; password: string }
    >({
      query: (credentials) => ({
        url: '/auth/login',
        method: 'POST',
        body: credentials,
      }),
    }),
    getMe: builder.query<
      { id: number; username: string; email: string; roles: string[]; is_active: boolean },
      void
    >({
      query: () => '/auth/me',
    }),
    getUserPermissions: builder.query<UserPermissions, void>({
      query: () => '/auth/me/permissions',
      providesTags: ['Permissions'],
    }),
    getSsoConfig: builder.query<
      { enabled: boolean; url: string; realm: string; client_id: string },
      void
    >({
      query: () => '/auth/sso/config',
    }),
    ssoExchange: builder.mutation<
      { access_token: string; refresh_token: string; token_type: string },
      { code: string; redirect_uri: string; code_verifier: string }
    >({
      query: (body) => ({
        url: '/auth/oidc/exchange',
        method: 'POST',
        body,
      }),
    }),
  }),
});

export const {
  useLoginMutation,
  useGetMeQuery,
  useGetUserPermissionsQuery,
  useGetSsoConfigQuery,
  useSsoExchangeMutation,
} = authApi;
