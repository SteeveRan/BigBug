/**
 * @file api/pipelines.ts
 * @description Pipeline Runs endpoints
 * @dependencies api/base.ts
 */

import type { PipelineRun, PipelineRunCreate, PipelineRunList } from '../../types';
import { api } from './base';

export const pipelinesApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getPipelineRuns: builder.query<PipelineRunList, { page?: number; status?: number }>({
      query: (params) => ({ url: '/pipelines', params }),
      providesTags: ['Pipeline'],
    }),
    getPipelineRun: builder.query<PipelineRun, number>({
      query: (id) => `/pipelines/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Pipeline', id }],
    }),
    triggerPipeline: builder.mutation<PipelineRun, PipelineRunCreate>({
      query: (data) => ({ url: '/pipelines', method: 'POST', body: data }),
      invalidatesTags: ['Pipeline'],
    }),
    cancelPipeline: builder.mutation<PipelineRun, number>({
      query: (id) => ({ url: `/pipelines/${id}/cancel`, method: 'POST' }),
      invalidatesTags: ['Pipeline'],
    }),
    retryPipeline: builder.mutation<PipelineRun, number>({
      query: (id) => ({ url: `/pipelines/${id}/retry`, method: 'POST' }),
      invalidatesTags: ['Pipeline'],
    }),
  }),
});

export const {
  useGetPipelineRunsQuery,
  useGetPipelineRunQuery,
  useTriggerPipelineMutation,
  useCancelPipelineMutation,
  useRetryPipelineMutation,
} = pipelinesApi;
