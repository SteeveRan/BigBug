/**
 * @file splitMyProviders.test.ts
 * @description Unit tests for the splitMyProviders client-side helper.
 */

import { describe, it, expect } from 'vitest';
import { splitMyProviders } from '../../pages/Profile/splitMyProviders';
import type { ResourceProvider } from '../../types';

function provider(overrides: Partial<ResourceProvider> = {}): ResourceProvider {
  return {
    id: 1,
    domain: 'git',
    subtype: 'github',
    category: 'private',
    direction: 'external',
    name: 'github-main',
    label: 'GitHub',
    description: null,
    base_url: null,
    config: {},
    credential_id: null,
    owner_user_id: null,
    visibility: 'owner',
    team_id: null,
    team_name: null,
    is_active: true,
    is_default: false,
    is_protected: false,
    verify_ssl: true,
    priority: 0,
    status_flag: 0,
    status_text: 'OK',
    last_checked_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    has_credential: false,
    ...overrides,
  };
}

describe('splitMyProviders', () => {
  it('puts user-owned providers into owned regardless of visibility', () => {
    const ownedPublic = provider({ id: 1, owner_user_id: 7, visibility: 'public' });
    const ownedPrivate = provider({ id: 2, owner_user_id: 7, visibility: 'owner' });
    const someoneElse = provider({ id: 3, owner_user_id: 8, visibility: 'private' });

    const { owned, shared } = splitMyProviders(
      [ownedPublic, ownedPrivate, someoneElse],
      7,
      new Set<number>()
    );

    expect(owned.map((p) => p.id)).toEqual([1, 2]);
    expect(shared).toEqual([]);
  });

  it('puts team-shared providers for my teams into shared', () => {
    const teamProvider = provider({ id: 10, visibility: 'team', team_id: 5 });
    const otherTeamProvider = provider({ id: 11, visibility: 'team', team_id: 99 });

    const { owned, shared } = splitMyProviders([teamProvider, otherTeamProvider], 7, new Set([5]));

    expect(owned).toEqual([]);
    expect(shared.map((p) => p.id)).toEqual([10]);
  });

  it('excludes team-shared providers of teams the user is not a member of (admin case)', () => {
    // Админ видит все команды, но `myTeamIds` содержит только команды членства.
    const notMyTeamProvider = provider({ id: 20, visibility: 'team', team_id: 999 });

    const { shared } = splitMyProviders([notMyTeamProvider], 7, new Set<number>());

    expect(shared).toEqual([]);
  });

  it('does not put public provider of another user anywhere', () => {
    const foreignPublic = provider({ id: 30, owner_user_id: 8, visibility: 'public' });

    const { owned, shared } = splitMyProviders([foreignPublic], 7, new Set([1]));

    expect(owned).toEqual([]);
    expect(shared).toEqual([]);
  });

  it('handles undefined userId safely', () => {
    const ownedProvider = provider({ id: 40, owner_user_id: 7, visibility: 'owner' });

    const { owned } = splitMyProviders([ownedProvider], undefined, new Set([1]));

    expect(owned).toEqual([]);
  });
});
