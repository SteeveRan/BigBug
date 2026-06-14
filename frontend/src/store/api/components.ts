/**
 * @file api/components.ts
 * @description GitLab Components CRUD + run
 * @dependencies api/base.ts
 */

import type {
  PipelineRun,
  GitLabComponent,
  GitLabComponentCreate,
  GitLabComponentUpdate,
} from '../../types';
import { api } from './base';

export const componentsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getComponents: builder.query<GitLabComponent[], void>({
      query: () => '/components',
      providesTags: ['Component'],
    }),
    createComponent: builder.mutation<GitLabComponent, GitLabComponentCreate>({
      query: (data) => ({ url: '/components', method: 'POST', body: data }),
      invalidatesTags: ['Component'],
    }),
    updateComponent: builder.mutation<GitLabComponent, { id: number; data: GitLabComponentUpdate }>(
      {
        query: ({ id, data }) => ({ url: `/components/${id}`, method: 'PATCH', body: data }),
        invalidatesTags: (_result, _error, { id }) => [{ type: 'Component', id }, 'Component'],
      }
    ),
    deleteComponent: builder.mutation<void, number>({
      query: (id) => ({ url: `/components/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Component'],
    }),
    runComponent: builder.mutation<
      PipelineRun,
      { componentId: number; data: { ref: string; inputs: Record<string, string> } }
    >({
      query: ({ componentId, data }) => ({
        url: `/components/${componentId}/run`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Component', 'Pipeline'],
    }),
  }),
});

export const {
  useGetComponentsQuery,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
  useRunComponentMutation,
} = componentsApi;
