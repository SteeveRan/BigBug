import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type { RootState } from './index'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: `${BASE_URL}/api`,
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.accessToken
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      }
      return headers
    },
  }),
  tagTypes: ['Project', 'Mirror', 'GoldImage', 'AppImage', 'User', 'SyncLog', 'BuildLog'],
  endpoints: (builder) => ({
    // Auth
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

    // Projects
    listProjects: builder.query<unknown[], void>({
      query: () => '/projects',
      providesTags: ['Project'],
    }),
    getProject: builder.query<unknown, number>({
      query: (id) => `/projects/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Project', id }],
    }),
    createProject: builder.mutation<unknown, { github_url: string }>({
      query: (body) => ({ url: '/projects', method: 'POST', body }),
      invalidatesTags: ['Project'],
    }),
    importProject: builder.mutation<unknown, { github_url: string; gitlab_url?: string }>({
      query: (body) => ({ url: '/projects/import', method: 'POST', body }),
      invalidatesTags: ['Project'],
    }),
    updateProject: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/projects/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Project', id }],
    }),
    deleteProject: builder.mutation<void, number>({
      query: (id) => ({ url: `/projects/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Project'],
    }),
    refreshProject: builder.mutation<unknown, number>({
      query: (id) => ({ url: `/projects/${id}/refresh`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Project', id }],
    }),

    // Mirrors
    listMirrors: builder.query<unknown[], void>({
      query: () => '/mirrors',
      providesTags: ['Mirror'],
    }),
    getMirror: builder.query<unknown, number>({
      query: (id) => `/mirrors/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Mirror', id }],
    }),
    createMirror: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/mirrors', method: 'POST', body }),
      invalidatesTags: ['Mirror'],
    }),
    importMirror: builder.mutation<unknown, { github_url: string; gitlab_url: string }>({
      query: (body) => ({ url: '/mirrors/import', method: 'POST', body }),
      invalidatesTags: ['Mirror', 'Project'],
    }),
    triggerSync: builder.mutation<unknown, number>({
      query: (id) => ({ url: `/mirrors/${id}/sync`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'Mirror', id }, 'SyncLog'],
    }),
    getMirrorLogs: builder.query<unknown[], number>({
      query: (id) => `/mirrors/${id}/logs`,
      providesTags: ['SyncLog'],
    }),
    getMirrorSchedule: builder.query<unknown, number>({
      query: (id) => `/mirrors/${id}/schedule`,
    }),
    updateMirrorSchedule: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/mirrors/${id}/schedule`, method: 'PATCH', body: data }),
    }),

    // Gold Images
    listGoldImages: builder.query<unknown[], void>({
      query: () => '/gold-images',
      providesTags: ['GoldImage'],
    }),
    getGoldImage: builder.query<unknown, number>({
      query: (id) => `/gold-images/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'GoldImage', id }],
    }),
    createGoldImage: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/gold-images', method: 'POST', body }),
      invalidatesTags: ['GoldImage'],
    }),
    updateGoldImage: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/gold-images/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'GoldImage', id }],
    }),
    deleteGoldImage: builder.mutation<void, number>({
      query: (id) => ({ url: `/gold-images/${id}`, method: 'DELETE' }),
      invalidatesTags: ['GoldImage'],
    }),
    triggerGoldBuild: builder.mutation<unknown, { id: number; version_tag: string; arch: string }>({
      query: ({ id, ...body }) => ({ url: `/gold-images/${id}/build`, method: 'POST', body }),
      invalidatesTags: ['BuildLog'],
    }),

    // App Images
    listAppImages: builder.query<unknown[], void>({
      query: () => '/app-images',
      providesTags: ['AppImage'],
    }),
    getAppImage: builder.query<unknown, number>({
      query: (id) => `/app-images/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'AppImage', id }],
    }),
    createAppImage: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/app-images', method: 'POST', body }),
      invalidatesTags: ['AppImage'],
    }),
    updateAppImage: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/app-images/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'AppImage', id }],
    }),
    deleteAppImage: builder.mutation<void, number>({
      query: (id) => ({ url: `/app-images/${id}`, method: 'DELETE' }),
      invalidatesTags: ['AppImage'],
    }),
    triggerAppBuild: builder.mutation<unknown, { id: number; version_tag: string; arch: string }>({
      query: ({ id, ...body }) => ({ url: `/app-images/${id}/build`, method: 'POST', body }),
      invalidatesTags: ['BuildLog'],
    }),

    // Admin
    listUsers: builder.query<unknown[], void>({
      query: () => '/admin/users',
      providesTags: ['User'],
    }),
    createUser: builder.mutation<unknown, Record<string, unknown>>({
      query: (body) => ({ url: '/admin/users', method: 'POST', body }),
      invalidatesTags: ['User'],
    }),
    updateUser: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/admin/users/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: ['User'],
    }),
    deleteUser: builder.mutation<void, number>({
      query: (id) => ({ url: `/admin/users/${id}`, method: 'DELETE' }),
      invalidatesTags: ['User'],
    }),
    listRoles: builder.query<unknown[], void>({
      query: () => '/admin/roles',
    }),
  }),
})

export const {
  useLoginMutation,
  useGetMeQuery,
  useListProjectsQuery,
  useGetProjectQuery,
  useCreateProjectMutation,
  useImportProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
  useRefreshProjectMutation,
  useListMirrorsQuery,
  useGetMirrorQuery,
  useCreateMirrorMutation,
  useImportMirrorMutation,
  useTriggerSyncMutation,
  useGetMirrorLogsQuery,
  useGetMirrorScheduleQuery,
  useUpdateMirrorScheduleMutation,
  useListGoldImagesQuery,
  useGetGoldImageQuery,
  useCreateGoldImageMutation,
  useUpdateGoldImageMutation,
  useDeleteGoldImageMutation,
  useTriggerGoldBuildMutation,
  useListAppImagesQuery,
  useGetAppImageQuery,
  useCreateAppImageMutation,
  useUpdateAppImageMutation,
  useDeleteAppImageMutation,
  useTriggerAppBuildMutation,
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
  useListRolesQuery,
} = api
