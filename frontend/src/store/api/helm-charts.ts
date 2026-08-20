/**
 * @file api/helm-charts.ts
 * @description Helm Charts CRUD + index/mirror/versions/logs + Sync Schedules
 * @dependencies api/base.ts
 */

import type {
  HelmChartSource,
  HelmChartSourceDetail,
  HelmChartVersion,
  HelmSyncLog,
  HelmSyncSchedule,
} from '../../types';
import { api } from './base';

export const helmChartsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    // ── Helm Charts CRUD ───────────────────────────────────────────────

    listHelmCharts: builder.query<HelmChartSource[], void>({
      query: () => '/helm-charts',
      providesTags: ['HelmChart'],
    }),
    getHelmChart: builder.query<HelmChartSourceDetail, number>({
      query: (id) => `/helm-charts/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'HelmChart', id }],
    }),
    createHelmChart: builder.mutation<
      HelmChartSource,
      {
        name: string;
        repo_url: string;
        description?: string;
        provider_id?: number;
        target_repo_url?: string;
      }
    >({
      query: (body) => ({ url: '/helm-charts', method: 'POST', body }),
      invalidatesTags: ['HelmChart'],
    }),
    updateHelmChart: builder.mutation<
      HelmChartSource,
      { id: number; data: Partial<HelmChartSource> }
    >({
      query: ({ id, data }) => ({ url: `/helm-charts/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'HelmChart', id }],
    }),
    deleteHelmChart: builder.mutation<void, number>({
      query: (id) => ({ url: `/helm-charts/${id}`, method: 'DELETE' }),
      invalidatesTags: ['HelmChart'],
    }),

    // ── Index / Mirror ─────────────────────────────────────────────────

    indexHelmChart: builder.mutation<HelmSyncLog, number>({
      query: (id) => ({ url: `/helm-charts/${id}/index`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'HelmChart', id }],
    }),
    mirrorHelmChart: builder.mutation<
      HelmSyncLog,
      { id: number; chart_name: string; version: string }
    >({
      query: ({ id, chart_name, version }) => ({
        url: `/helm-charts/${id}/mirror?chart_name=${encodeURIComponent(chart_name)}&version=${encodeURIComponent(version)}`,
        method: 'POST',
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'HelmChart', id }, 'HelmChart'],
    }),

    // ── Versions / Logs ────────────────────────────────────────────────

    getHelmChartVersions: builder.query<HelmChartVersion[], number>({
      query: (id) => `/helm-charts/${id}/versions`,
    }),
    getHelmChartLogs: builder.query<HelmSyncLog[], number>({
      query: (id) => `/helm-charts/${id}/logs`,
    }),

    // ── Sync Schedules ─────────────────────────────────────────────────

    getHelmSyncSchedules: builder.query<HelmSyncSchedule[], number>({
      query: (sourceId) => `/helm-charts/${sourceId}/schedule`,
      providesTags: (_result, _error, sourceId) => [{ type: 'HelmSyncSchedule', id: sourceId }],
    }),
    createHelmSyncSchedule: builder.mutation<
      HelmSyncSchedule,
      {
        sourceId: number;
        data: { cron_expression?: string; is_enabled?: boolean; use_default_schedule?: boolean };
      }
    >({
      query: ({ sourceId, data }) => ({
        url: `/helm-charts/${sourceId}/schedule`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'HelmSyncSchedule', id: sourceId },
      ],
    }),
    updateHelmSyncSchedule: builder.mutation<
      HelmSyncSchedule,
      {
        sourceId: number;
        scheduleId: number;
        data: { cron_expression?: string; is_enabled?: boolean; use_default_schedule?: boolean };
      }
    >({
      query: ({ sourceId, scheduleId, data }) => ({
        url: `/helm-charts/${sourceId}/schedule/${scheduleId}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'HelmSyncSchedule', id: sourceId },
      ],
    }),
    deleteHelmSyncSchedule: builder.mutation<void, { sourceId: number; scheduleId: number }>({
      query: ({ sourceId, scheduleId }) => ({
        url: `/helm-charts/${sourceId}/schedule/${scheduleId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, { sourceId }) => [
        { type: 'HelmSyncSchedule', id: sourceId },
      ],
    }),
  }),
});

export const {
  useListHelmChartsQuery,
  useGetHelmChartQuery,
  useCreateHelmChartMutation,
  useUpdateHelmChartMutation,
  useDeleteHelmChartMutation,
  useIndexHelmChartMutation,
  useMirrorHelmChartMutation,
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
  useGetHelmSyncSchedulesQuery,
  useCreateHelmSyncScheduleMutation,
  useUpdateHelmSyncScheduleMutation,
  useDeleteHelmSyncScheduleMutation,
} = helmChartsApi;
