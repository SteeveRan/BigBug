/**
 * @file api/teams.ts
 * @description Teams RTK Query endpoints (`/api/teams`).
 * @dependencies api/base.ts
 */

import type {
  ResourceProvider,
  Team,
  TeamCreate,
  TeamMember,
  TeamMemberAdd,
  TeamUpdate,
} from '../../types';
import { api } from './base';

export const teamsApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getTeams: builder.query<Team[], void>({
      query: () => '/teams',
      providesTags: ['Team'],
    }),
    createTeam: builder.mutation<Team, TeamCreate>({
      query: (body) => ({ url: '/teams', method: 'POST', body }),
      invalidatesTags: ['Team'],
    }),
    updateTeam: builder.mutation<Team, { id: number; data: TeamUpdate }>({
      query: ({ id, data }) => ({ url: `/teams/${id}`, method: 'PATCH', body: data }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Team', id }, 'Team'],
    }),
    deleteTeam: builder.mutation<void, number>({
      query: (id) => ({ url: `/teams/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Team'],
    }),
    getTeamMembers: builder.query<TeamMember[], number>({
      query: (teamId) => `/teams/${teamId}/members`,
      providesTags: (_result, _error, teamId) => [{ type: 'Team', id: teamId }],
    }),
    addTeamMember: builder.mutation<TeamMember, { teamId: number; data: TeamMemberAdd }>({
      query: ({ teamId, data }) => ({
        url: `/teams/${teamId}/members`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (_result, _error, { teamId }) => [{ type: 'Team', id: teamId }],
    }),
    removeTeamMember: builder.mutation<void, { teamId: number; userId: number }>({
      query: ({ teamId, userId }) => ({
        url: `/teams/${teamId}/members/${userId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, { teamId }) => [{ type: 'Team', id: teamId }],
    }),
    getTeamProviders: builder.query<ResourceProvider[], number>({
      query: (teamId) => `/teams/${teamId}/providers`,
      providesTags: ['Provider'],
    }),
  }),
});

export const {
  useGetTeamsQuery,
  useCreateTeamMutation,
  useUpdateTeamMutation,
  useDeleteTeamMutation,
  useGetTeamMembersQuery,
  useAddTeamMemberMutation,
  useRemoveTeamMemberMutation,
  useGetTeamProvidersQuery,
} = teamsApi;
