/**
 * @file api/oidc-config.ts
 * @description OIDC Configuration endpoints
 * @dependencies api/base.ts
 */

import type { OIDCConfig, OIDCConfigUpdate } from '../../types';
import { api } from './base';

export const oidcConfigApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getOidcConfig: builder.query<OIDCConfig, void>({
      query: () => '/auth/admin/oidc-config',
      providesTags: ['OIDCConfig'],
    }),
    updateOidcConfig: builder.mutation<OIDCConfig, OIDCConfigUpdate>({
      query: (data) => ({
        url: '/auth/admin/oidc-config',
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: ['OIDCConfig'],
    }),
  }),
});

export const {
  useGetOidcConfigQuery,
  useUpdateOidcConfigMutation,
} = oidcConfigApi;
