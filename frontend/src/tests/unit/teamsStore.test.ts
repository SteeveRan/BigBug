/**
 * @file teamsStore.test.ts
 * @description Contract tests for Teams RTK Query endpoints: each endpoint
 *   dispatches the right HTTP method to the right URL (verified through a
 *   stubbed global fetch via a real RTK Query store).
 * @dependencies Vitest, RTK Query
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import { teamsApi } from '../../store/api/teams';

// jsdom's AbortSignal fails undici's brand check inside RTK fetchBaseQuery
// (Request comes from Node undici, signal from jsdom realm) — same reason
// SsoCallback.test.tsx mocks its mutation. Patch Request to skip the check;
// RTK passes its own signal for aborting, which no unit contract test needs.
class TestRequest extends globalThis.Request {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    super(input, { ...init, signal: undefined });
  }
}

function createApiStore() {
  return configureStore({
    reducer: { [teamsApi.reducerPath]: teamsApi.reducer },
    middleware: (gdm) => gdm().concat(teamsApi.middleware),
  });
}

const fetchMock = vi.fn();
let lastFetchArgs: [RequestInfo | string, RequestInit?] = ['', undefined];

beforeEach(() => {
  vi.stubGlobal('Request', TestRequest);
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  lastFetchArgs = ['', undefined];
});

function stubFetch(status = 200, body: unknown = []) {
  fetchMock.mockImplementation(async (...args: unknown[]) => {
    lastFetchArgs = args as [RequestInfo | string, RequestInit?];
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
}

/** fetchBaseQuery passes a Request object (or a URL string) — normalize to url+method+body. */
async function fetchCall(): Promise<{ url: string; method: string; body: unknown }> {
  const [input, init] = lastFetchArgs;
  if (typeof input === 'string') {
    return { url: input, method: init?.method ?? 'GET', body: init?.body ?? null };
  }
  const clone = input.clone();
  const bodyText = init?.body ? String(init.body) : await clone.text();
  return { url: input.url, method: input.method, body: bodyText || null };
}

describe('teamsStore — endpoint contracts', () => {
  it('getTeams issues GET /teams', async () => {
    stubFetch();
    const store = createApiStore();
    await store.dispatch(teamsApi.endpoints.getTeams.initiate());
    const { url, method } = await fetchCall();
    expect(url).toContain('/teams');
    expect(method).toBe('GET');
  });

  it('createTeam issues POST /teams with body', async () => {
    stubFetch(201, { id: 1, name: 't' });
    const store = createApiStore();
    await store.dispatch(teamsApi.endpoints.createTeam.initiate({ name: 't', owner_user_id: 1 }));
    const { url, method, body } = await fetchCall();
    expect(url).toContain('/teams');
    expect(method).toBe('POST');
    expect(JSON.parse(String(body))).toEqual({ name: 't', owner_user_id: 1 });
  });

  it('updateTeam issues PATCH /teams/{id}', async () => {
    stubFetch(200, { id: 3, name: 'x' });
    const store = createApiStore();
    await store.dispatch(teamsApi.endpoints.updateTeam.initiate({ id: 3, data: { name: 'x' } }));
    const { url, method } = await fetchCall();
    expect(url).toContain('/teams/3');
    expect(method).toBe('PATCH');
  });

  it('deleteTeam issues DELETE /teams/{id}', async () => {
    stubFetch(200, null);
    const store = createApiStore();
    await store.dispatch(teamsApi.endpoints.deleteTeam.initiate(3));
    const { url, method } = await fetchCall();
    expect(url).toContain('/teams/3');
    expect(method).toBe('DELETE');
  });

  it('getTeamMembers issues GET /teams/{id}/members', async () => {
    stubFetch();
    const store = createApiStore();
    await store.dispatch(teamsApi.endpoints.getTeamMembers.initiate(7));
    const { url } = await fetchCall();
    expect(url).toContain('/teams/7/members');
  });

  it('getTeamProviders issues GET /teams/{id}/providers', async () => {
    stubFetch();
    const store = createApiStore();
    await store.dispatch(teamsApi.endpoints.getTeamProviders.initiate(7));
    const { url } = await fetchCall();
    expect(url).toContain('/teams/7/providers');
  });
});
