import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

// SSO_REDIRECT_URI = window.location.origin + '/sso/callback' is evaluated
// at module import time.  In jsdom the default origin is http://localhost:3000
// so the tests must match that value.
const DEFAULT_ORIGIN = 'http://localhost:3000';

import { useKeycloakAuth } from '../../hooks/useKeycloakAuth';

// Mock RTK Query
vi.mock('../../store/api', () => ({
  useGetSsoConfigQuery: vi.fn(),
}));

import { useGetSsoConfigQuery } from '../../store/api';

// Mock sessionStorage
const mockStorage: Record<string, string> = {};
beforeEach(() => {
  vi.clearAllMocks();
  Object.keys(mockStorage).forEach((k) => delete mockStorage[k]);

  Object.defineProperty(window, 'sessionStorage', {
    value: {
      getItem: vi.fn((key: string) => mockStorage[key] ?? null),
      setItem: vi.fn((key: string, value: string) => {
        mockStorage[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete mockStorage[key];
      }),
    },
    configurable: true,
    writable: true,
  });
});

// Mock window.location
beforeEach(() => {
  vi.stubGlobal('location', {
    href: '',
    origin: DEFAULT_ORIGIN,
    search: '',
    assign: vi.fn(),
  });
});

// ─── Helpers ─────────────────────────────────────────────────────────────
const providerA = {
  id: 1,
  name: 'Provider A',
  url: 'https://kc.example.com',
  realm: 'r1',
  client_id: 'c1',
};
const providerB = {
  id: 2,
  name: 'Provider B',
  url: 'https://other.example.com',
  realm: 'r2',
  client_id: 'c2',
};

const mockSsoConfig = (overrides: Record<string, unknown> = {}) => {
  (useGetSsoConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: {
      enabled: true,
      providers: [providerA],
      ...overrides,
    },
    isLoading: false,
    isError: false,
    error: null,
  });
};

// ─── Tests ───────────────────────────────────────────────────────────────
describe('useKeycloakAuth', () => {
  it('returns ready=true with providers when SSO is enabled', async () => {
    mockSsoConfig();

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.enabled).toBe(true);
    expect(result.current.providers).toEqual([providerA]);
    expect(result.current.error).toBeNull();
  });

  it('returns enabled=false when config.enabled=false (master switch)', async () => {
    mockSsoConfig({ enabled: false });

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.enabled).toBe(false);
    expect(result.current.providers).toEqual([]);
  });

  it('returns enabled=false when the provider list is empty', async () => {
    mockSsoConfig({ providers: [] });

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.enabled).toBe(false);
    expect(result.current.providers).toEqual([]);
  });

  it('returns ready=true but enabled=false when config is null (error)', async () => {
    (useGetSsoConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: null,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
    });

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.enabled).toBe(false);
  });

  it('login(provider) builds a redirect URL for that provider', async () => {
    mockSsoConfig({ providers: [providerA, providerB] });

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    // login() redirects the browser — catches the "never" promise
    try {
      await result.current.login(providerB);
    } catch {
      // Expected
    }

    expect(window.location.href).toContain(
      'https://other.example.com/realms/r2/protocol/openid-connect/auth'
    );
    expect(window.location.href).toContain('response_type=code');
    expect(window.location.href).toContain('code_challenge_method=S256');
    expect(window.location.href).toContain(
      'redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fsso%2Fcallback'
    );
  });

  it('login() is a no-op when no provider is given', async () => {
    mockSsoConfig({ enabled: false });

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    await result.current.login(undefined as never);
    expect(window.location.href).toBe('');
  });

  it('handleCallback() extracts code, verifier and provider_id (state wins)', () => {
    mockSsoConfig();

    // Simulate callback URL with state carrying the provider_id
    window.location.search = '?code=auth-code-123&state=2';

    // Pre-populate sessionStorage with a verifier and a (stale) provider id
    mockStorage['sso_code_verifier'] = 'my-verifier';
    mockStorage['sso_provider_id'] = '1';

    const { result } = renderHook(() => useKeycloakAuth());

    const payload = result.current.handleCallback();

    // DEFAULT_ORIGIN = http://localhost:3000 (jsdom default)
    expect(payload).toEqual({
      code: 'auth-code-123',
      redirect_uri: `${DEFAULT_ORIGIN}/sso/callback`,
      code_verifier: 'my-verifier',
      provider_id: 2,
      state: '2',
    });
  });

  it('handleCallback() falls back to sessionStorage provider_id when state is absent', () => {
    mockSsoConfig();

    window.location.search = '?code=auth-code-123';
    mockStorage['sso_code_verifier'] = 'my-verifier';
    mockStorage['sso_provider_id'] = '7';

    const { result } = renderHook(() => useKeycloakAuth());

    const payload = result.current.handleCallback();
    expect('provider_id' in payload && payload.provider_id).toBe(7);
    expect('state' in payload && payload.state).toBe('7');
  });

  it('handleCallback() returns error when ?error=access_denied is present', () => {
    mockSsoConfig();

    window.location.search = '?error=access_denied&error_description=User+denied';

    const { result } = renderHook(() => useKeycloakAuth());

    const payload = result.current.handleCallback();

    expect('error' in payload).toBe(true);
    expect((payload as { error: string }).error).toBe('User denied');
  });

  it('handleCallback() returns error when code is missing', () => {
    mockSsoConfig();

    window.location.search = '?session_state=abc';

    const { result } = renderHook(() => useKeycloakAuth());

    const payload = result.current.handleCallback();

    expect('error' in payload).toBe(true);
    expect((payload as { error: string }).error).toContain('Authorization code missing');
  });

  it('handleCallback() returns error when verifier is not in sessionStorage', () => {
    mockSsoConfig();

    window.location.search = '?code=some-code&state=1';

    const { result } = renderHook(() => useKeycloakAuth());

    const payload = result.current.handleCallback();

    expect('error' in payload).toBe(true);
    expect((payload as { error: string }).error).toContain('code_verifier not found');
  });

  it('handleCallback() returns error when provider_id is missing entirely', () => {
    mockSsoConfig();

    window.location.search = '?code=some-code';
    mockStorage['sso_code_verifier'] = 'my-verifier';

    const { result } = renderHook(() => useKeycloakAuth());

    const payload = result.current.handleCallback();

    expect('error' in payload).toBe(true);
    expect((payload as { error: string }).error).toContain('provider_id missing');
  });
});
