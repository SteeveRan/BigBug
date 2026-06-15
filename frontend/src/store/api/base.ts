/**
 * @file api/base.ts
 * @description Базовый API-слайс — baseQuery, tagTypes. Эндпоинты инжектируются из отдельных файлов.
 *
 *              baseQuery обёрнут в customBaseQuery, который при любом 401-ответе
 *              автоматически выполняет logout — это гарантирует разлогин при
 *              протухшем токене независимо от того, какой эндпоинт был вызван.
 *
 * @dependencies @reduxjs/toolkit, store/index.ts (RootState), store/authSlice
 */

import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from '@reduxjs/toolkit/query/react';
import type { RootState } from '../index';
import { logout } from '../authSlice';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const rawBaseQuery = fetchBaseQuery({
  baseUrl: `${BASE_URL}/api`,
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.accessToken;
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    return headers;
  },
});

/**
 * Обёртка вокруг fetchBaseQuery, которая при получении 401-ответа
 * автоматически диспатчит logout(), очищая состояние авторизации
 * и перенаправляя пользователя на /login.
 */
const customBaseQuery: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, api, extraOptions) => {
  const result = await rawBaseQuery(args, api, extraOptions);

  if (result.error && result.error.status === 401) {
    api.dispatch(logout());
  }

  return result;
};

export const api = createApi({
  reducerPath: 'api',
  baseQuery: customBaseQuery,
  tagTypes: [
    'Project',
    'Mirror',
    'GoldImage',
    'AppImage',
    'User',
    'SyncLog',
    'BuildLog',
    'HelmChart',
    'DockerImage',
    'DockerSyncSchedule',
    'Permissions',
    'Roles',
    'RoleUsers',
    'RoleScope',
    'Integration',
    'OIDCConfig',
    'Pipeline',
    'Component',
    'AuditLog',
    'SourceProvider',
    'SourceGroup',
    'SourceRepository',
    'MirrorLog',
    'SyncGroup',
    'PipelineConfig',
    'OrphanedMirrors',
    'Reports',
  ],
  endpoints: () => ({}),
});
