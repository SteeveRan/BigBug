/**
 * @file api/gold-images.ts
 * @description Gold Images CRUD + build/scan/sign/verify
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

export const goldImagesApi = api.injectEndpoints({
  endpoints: (builder) => ({
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
    scanGoldImageVersion: builder.mutation<
      VulnerabilityScanResult,
      { imageId: number; versionId: number } & ScanRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/gold-images/${imageId}/versions/${versionId}/scan`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['GoldImage'],
    }),
    getGoldImageScanResults: builder.mutation<
      VulnerabilityScanResult,
      { imageId: number; versionId: number } & ScanRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/gold-images/${imageId}/versions/${versionId}/scan/results`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['GoldImage'],
    }),
    signGoldImageVersion: builder.mutation<
      SignImageResult,
      { imageId: number; versionId: number } & SignImageRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/gold-images/${imageId}/versions/${versionId}/sign`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['GoldImage'],
    }),
    verifyGoldImageVersion: builder.mutation<
      VerifyImageResult,
      { imageId: number; versionId: number } & VerifyImageRequest
    >({
      query: ({ imageId, versionId, ...body }) => ({
        url: `/gold-images/${imageId}/versions/${versionId}/verify`,
        method: 'POST',
        body,
      }),
    }),
  }),
});

export const {
  useListGoldImagesQuery,
  useGetGoldImageQuery,
  useCreateGoldImageMutation,
  useUpdateGoldImageMutation,
  useDeleteGoldImageMutation,
  useTriggerGoldBuildMutation,
  useScanGoldImageVersionMutation,
  useGetGoldImageScanResultsMutation,
  useSignGoldImageVersionMutation,
  useVerifyGoldImageVersionMutation,
} = goldImagesApi;
