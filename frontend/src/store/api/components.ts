/**
 * @file api/components.ts
 * @description GitLab Components CRUD + run + presets + push/pull
 * @dependencies api/base.ts
 */

import type {
  PipelineRun,
  GitLabComponent,
  GitLabComponentCreate,
  GitLabComponentUpdate,
  ComponentPreset,
  ComponentPushIn,
  ComponentPullOut,
} from '../../types';
import { api } from './base';

export const componentsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getComponents: builder.query<GitLabComponent[], { gitlab_project_id?: number } | void>({
      query: (params) => ({ url: '/components', params: params ?? undefined }),
      providesTags: ['Component'],
    }),
    getComponentPresets: builder.query<ComponentPreset[], void>({
      query: () => '/components/presets',
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
    pushComponent: builder.mutation<GitLabComponent, { id: number; data: ComponentPushIn }>({
      query: ({ id, data }) => ({ url: `/components/${id}/push`, method: 'POST', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Component', id }, 'Component'],
    }),
    pullComponent: builder.mutation<ComponentPullOut, number>({
      query: (id) => ({ url: `/components/${id}/pull`, method: 'POST' }),
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
  useGetComponentPresetsQuery,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
  usePushComponentMutation,
  usePullComponentMutation,
  useRunComponentMutation,
} = componentsApi;
