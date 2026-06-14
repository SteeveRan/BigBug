/**
 * @file api/pipeline-configs.ts
 * @description Pipeline Configurations CRUD + duplicate
 * @dependencies api/base.ts
 */

import type { PipelineConfig, PipelineConfigCreate, PipelineConfigUpdate } from '../../types';
import { api } from './base';

export const pipelineConfigsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getPipelineConfigs: builder.query<
      PipelineConfig[],
      { search?: string; is_enabled?: boolean } | void
    >({
      query: (params) => ({ url: '/pipelines/configs', params: params ?? undefined }),
      providesTags: ['PipelineConfig'],
    }),
    getPipelineConfig: builder.query<PipelineConfig, number>({
      query: (id) => `/pipelines/configs/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'PipelineConfig', id }],
    }),
    createPipelineConfig: builder.mutation<PipelineConfig, PipelineConfigCreate>({
      query: (data) => ({ url: '/pipelines/configs', method: 'POST', body: data }),
      invalidatesTags: ['PipelineConfig'],
    }),
    updatePipelineConfig: builder.mutation<
      PipelineConfig,
      { id: number; data: PipelineConfigUpdate }
    >({
      query: ({ id, data }) => ({ url: `/pipelines/configs/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: 'PipelineConfig', id },
        'PipelineConfig',
      ],
    }),
    deletePipelineConfig: builder.mutation<void, number>({
      query: (id) => ({ url: `/pipelines/configs/${id}`, method: 'DELETE' }),
      invalidatesTags: ['PipelineConfig'],
    }),
    duplicatePipelineConfig: builder.mutation<PipelineConfig, { id: number; name: string }>({
      query: ({ id, name }) => ({
        url: `/pipelines/configs/${id}/duplicate`,
        method: 'POST',
        body: { name },
      }),
      invalidatesTags: ['PipelineConfig'],
    }),
  }),
});

export const {
  useGetPipelineConfigsQuery,
  useGetPipelineConfigQuery,
  useCreatePipelineConfigMutation,
  useUpdatePipelineConfigMutation,
  useDeletePipelineConfigMutation,
  useDuplicatePipelineConfigMutation,
} = pipelineConfigsApi;
