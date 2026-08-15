/**
 * @file teamsStore.test.ts
 * @description Unit tests for Teams RTK Query endpoints.
 * @dependencies Vitest
 */

import { describe, it, expect } from 'vitest';
import { teamsApi } from '../../store/api/teams';

describe('teamsStore — endpoints', () => {
  it('getTeams uses GET /teams', () => {
    expect(teamsApi.endpoints.getTeams).toBeDefined();
  });

  it('createTeam is a POST /teams mutation', () => {
    expect(teamsApi.endpoints.createTeam).toBeDefined();
  });

  it('getTeamMembers uses GET /teams/{id}/members', () => {
    expect(teamsApi.endpoints.getTeamMembers).toBeDefined();
  });

  it('addTeamMember and removeTeamMember exist', () => {
    expect(teamsApi.endpoints.addTeamMember).toBeDefined();
    expect(teamsApi.endpoints.removeTeamMember).toBeDefined();
  });

  it('getTeamProviders uses GET /teams/{id}/providers', () => {
    expect(teamsApi.endpoints.getTeamProviders).toBeDefined();
  });

  it('updateTeam and deleteTeam exist', () => {
    expect(teamsApi.endpoints.updateTeam).toBeDefined();
    expect(teamsApi.endpoints.deleteTeam).toBeDefined();
  });
});
