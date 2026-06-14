/**
 * @file api/app-images.ts
 * @description App Images CRUD + build/scan/sign/verify
 * @dependencies api/base.ts
 */

import type {
  VulnerabilityScanResult,
  ScanRequest,
  SignImageRequest,
  SignImageResult,
  VerifyImageRequest,
  VerifyImageResult,
} from '../../types';
import { api } from './base';

export const appImagesApi = api.injectEndpoints({
  endpoints: (builder) => ({
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
    scanAppImageVersion: builder.mutation<
      VulnerabilityScanResult,
      { imageId: number; versionId: number } & ScanRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/app-images/${imageId}/versions/${versionId}/scan`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['AppImage'],
    }),
    signAppImageVersion: builder.mutation<
      SignImageResult,
      { imageId: number; versionId: number } & SignImageRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/app-images/${imageId}/versions/${versionId}/sign`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['AppImage'],
    }),
    verifyAppImageVersion: builder.mutation<
      VerifyImageResult,
      { imageId: number; versionId: number } & VerifyImageRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/app-images/${imageId}/versions/${versionId}/verify`,
        method: 'POST',
        body,
      }),
    }),
  }),
});

export const {
  useListAppImagesQuery,
  useGetAppImageQuery,
  useCreateAppImageMutation,
  useUpdateAppImageMutation,
  useDeleteAppImageMutation,
  useTriggerAppBuildMutation,
  useScanAppImageVersionMutation,
  useSignAppImageVersionMutation,
  useVerifyAppImageVersionMutation,
} = appImagesApi;
