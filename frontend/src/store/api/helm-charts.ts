/**
 * @file api/helm-charts.ts
 * @description Helm Charts CRUD + index/versions/logs
 * @dependencies api/base.ts
 */

import { api } from './base';

export const helmChartsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    listHelmCharts: builder.query<unknown[], void>({
      query: () => '/helm-charts',
      providesTags: ['HelmChart'],
    }),
    getHelmChart: builder.query<unknown, number>({
      query: (id) => `/helm-charts/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'HelmChart', id }],
    }),
    createHelmChart: builder.mutation<
      unknown,
      { name: string; repo_url: string; description?: string }
    >({
      query: (body) => ({ url: '/helm-charts', method: 'POST', body }),
      invalidatesTags: ['HelmChart'],
    }),
    updateHelmChart: builder.mutation<unknown, { id: number; data: Record<string, unknown> }>({
      query: ({ id, data }) => ({ url: `/helm-charts/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'HelmChart', id }],
    }),
    deleteHelmChart: builder.mutation<void, number>({
      query: (id) => ({ url: `/helm-charts/${id}`, method: 'DELETE' }),
      invalidatesTags: ['HelmChart'],
    }),
    indexHelmChart: builder.mutation<unknown, number>({
      query: (id) => ({ url: `/helm-charts/${id}/index`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [{ type: 'HelmChart', id }],
    }),
    getHelmChartVersions: builder.query<unknown[], number>({
      query: (id) => `/helm-charts/${id}/versions`,
    }),
    getHelmChartLogs: builder.query<unknown[], number>({
      query: (id) => `/helm-charts/${id}/logs`,
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
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
} = helmChartsApi;
