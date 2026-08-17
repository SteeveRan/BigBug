/**
 * @file api/docker-images.ts
 * @description Docker Images CRUD + analyze/compare + Sync Schedules
 * @dependencies api/base.ts
 */

import type {
  DockerImageSource,
  DockerImageSourceDetail,
  DockerImageTag,
  DockerSyncLog,
  DockerSyncSchedule,
  DockerImageCompareResponse,
  AnalyzeImageResponse,
} from '../../types';
import { api } from './base';

export const dockerImagesApi = api.injectEndpoints({
  endpoints: (builder) => ({
    // ── Docker Images CRUD ────────────────────────────────────────────

    listDockerImages: builder.query<DockerImageSource[], void>({
      query: () => '/docker-images',
      providesTags: ['DockerImage'],
    }),
    getDockerImage: builder.query<DockerImageSourceDetail, number>({
      query: (id) => `/docker-images/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'DockerImage', id }],
    }),
    createDockerImage: builder.mutation<
      DockerImageSource,
      {
        name: string;
        registry_url: string;
        description?: string;
        image_name?: string;
        provider_id?: number;
        target_provider_id?: number;
        target_registry_url?: string;
        target_project?: string;
      }
    >({
      query: (body) => ({ url: '/docker-images', method: 'POST', body }),
      invalidatesTags: ['DockerImage'],
    }),
    updateDockerImage: builder.mutation<
      DockerImageSource,
      { id: number; data: Partial<DockerImageSource> }
    >({
      query: ({ id, data }) => ({ url: `/docker-images/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'DockerImage', id }],
    }),
    deleteDockerImage: builder.mutation<void, number>({
      query: (id) => ({ url: `/docker-images/${id}`, method: 'DELETE' }),
      invalidatesTags: ['DockerImage'],
    }),
    indexDockerImage: builder.mutation<unknown, { id: number; image_name: string }>({
      query: ({ id, image_name }) => ({
        url: `/docker-images/${id}/index?image_name=${encodeURIComponent(image_name)}`,
        method: 'POST',
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'DockerImage', id }],
    }),
    mirrorDockerImage: builder.mutation<DockerSyncLog, { id: number; image_name: string; tag: string }>({
      query: ({ id, image_name, tag }) => ({
        url: `/docker-images/${id}/mirror?image_name=${encodeURIComponent(image_name)}&tag=${encodeURIComponent(tag)}`,
        method: 'POST',
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'DockerImage', id }, 'DockerImage'],
    }),
    getDockerImageTags: builder.query<DockerImageTag[], number>({
      query: (id) => `/docker-images/${id}/tags`,
    }),
    getDockerImageLogs: builder.query<DockerSyncLog[], number>({
      query: (id) => `/docker-images/${id}/logs`,
    }),
    batchDeleteDockerTags: builder.mutation<void, { sourceId: number; tagIds: number[] }>({
      query: ({ sourceId, tagIds }) => ({
        url: `/docker-images/${sourceId}/tags/batch`,
        method: 'DELETE',
        body: { tag_ids: tagIds },
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [{ type: 'DockerImage', id: sourceId }],
    }),

    // ── Analyze / Compare ─────────────────────────────────────────────

    analyzeDockerImage: builder.mutation<AnalyzeImageResponse, { image_name: string }>({
      query: (body) => ({ url: '/docker-images/analyze', method: 'POST', body }),
    }),
    compareDockerImages: builder.query<
      DockerImageCompareResponse,
      { sourceAId: number; sourceBId: number }
    >({
      query: ({ sourceAId, sourceBId }) => `/docker-images/${sourceAId}/compare/${sourceBId}`,
    }),

    // ── Sync Schedules ─────────────────────────────────────────────────

    getDockerSyncSchedules: builder.query<DockerSyncSchedule[], number>({
      query: (sourceId) => `/docker-images/${sourceId}/schedule`,
      providesTags: (_result, _error, sourceId) => [{ type: 'DockerSyncSchedule', id: sourceId }],
    }),
    createDockerSyncSchedule: builder.mutation<
      DockerSyncSchedule,
      {
        sourceId: number;
        data: { cron_expression?: string; is_enabled?: boolean; use_default_schedule?: boolean };
      }
    >({
      query: ({ sourceId, data }) => ({
        url: `/docker-images/${sourceId}/schedule`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'DockerSyncSchedule', id: sourceId },
      ],
    }),
    updateDockerSyncSchedule: builder.mutation<
      DockerSyncSchedule,
      {
        sourceId: number;
        scheduleId: number;
        data: { cron_expression?: string; is_enabled?: boolean; use_default_schedule?: boolean };
      }
    >({
      query: ({ sourceId, scheduleId, data }) => ({
        url: `/docker-images/${sourceId}/schedule/${scheduleId}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'DockerSyncSchedule', id: sourceId },
      ],
    }),
    deleteDockerSyncSchedule: builder.mutation<void, { sourceId: number; scheduleId: number }>({
      query: ({ sourceId, scheduleId }) => ({
        url: `/docker-images/${sourceId}/schedule/${scheduleId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'DockerSyncSchedule', id: sourceId },
      ],
    }),
  }),
});

export const {
  useListDockerImagesQuery,
  useGetDockerImageQuery,
  useCreateDockerImageMutation,
  useUpdateDockerImageMutation,
  useDeleteDockerImageMutation,
  useIndexDockerImageMutation,
  useMirrorDockerImageMutation,
  useGetDockerImageTagsQuery,
  useGetDockerImageLogsQuery,
  useBatchDeleteDockerTagsMutation,
  useAnalyzeDockerImageMutation,
  useCompareDockerImagesQuery,
  useGetDockerSyncSchedulesQuery,
  useCreateDockerSyncScheduleMutation,
  useUpdateDockerSyncScheduleMutation,
  useDeleteDockerSyncScheduleMutation,
} = dockerImagesApi;
