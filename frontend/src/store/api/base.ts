/**
 * @file api/base.ts
 * @description Базовый API-слайс — baseQuery, tagTypes. Эндпоинты инжектируются из отдельных файлов.
 * @dependencies @reduxjs/toolkit, store/index.ts (RootState)
 */

import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { RootState } from '../index';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: `${BASE_URL}/api`,
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.accessToken;
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
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
