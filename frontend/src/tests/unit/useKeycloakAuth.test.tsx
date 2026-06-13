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
const mockSsoConfig = (overrides: Record<string, unknown> = {}) => {
  (useGetSsoConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: {
      enabled: true,
      url: 'https://kc.example.com',
      realm: 'myrealm',
      client_id: 'myclient',
      ...overrides,
    },
    isLoading: false,
    isError: false,
    error: null,
  });
};

// ─── Tests ───────────────────────────────────────────────────────────────
describe('useKeycloakAuth', () => {
  it('returns ready=true when config is loaded (SSO enabled)', async () => {
    mockSsoConfig();

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.enabled).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('returns ready=true but enabled=false when config.enabled=false', async () => {
    mockSsoConfig({ enabled: false });

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.enabled).toBe(false);
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

  it('login() build a redirect URL and sets window.location.href', async () => {
    mockSsoConfig();

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    // login() redirects the browser — catches the "never" promise
    try {
      await result.current.login();
    } catch {
      // Expected
    }

    expect(window.location.href).toContain(
      'https://kc.example.com/realms/myrealm/protocol/openid-connect/auth'
    );
    expect(window.location.href).toContain('response_type=code');
    expect(window.location.href).toContain('code_challenge_method=S256');
    expect(window.location.href).toContain(
      'redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fsso%2Fcallback'
    );
  });

  it('login() is a no-op when SSO is not enabled', async () => {
    mockSsoConfig({ enabled: false });

    const { result } = renderHook(() => useKeycloakAuth());

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    await result.current.login();
    expect(window.location.href).toBe('');
  });

  it('handleCallback() extracts code from URL and verifier from sessionStorage', () => {
    mockSsoConfig();

    // Simulate callback URL
    window.location.search = '?code=auth-code-123&session_state=abc';

    // Pre-populate sessionStorage with a verifier
    mockStorage['sso_code_verifier'] = 'my-verifier';

    const { result } = renderHook(() => useKeycloakAuth());

    const payload = result.current.handleCallback();

    // DEFAULT_ORIGIN = http://localhost:3000 (jsdom default)
    expect(payload).toEqual({
      code: 'auth-code-123',
      redirect_uri: `${DEFAULT_ORIGIN}/sso/callback`,
      code_verifier: 'my-verifier',
    });
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

    window.location.search = '?code=some-code';

    const { result } = renderHook(() => useKeycloakAuth());

    const payload = result.current.handleCallback();

    expect('error' in payload).toBe(true);
    expect((payload as { error: string }).error).toContain('code_verifier not found');
  });
});
