import { describe, it, expect, beforeEach, vi } from 'vitest';

import {
  generateCodeVerifier,
  computeCodeChallenge,
  redirectToKeycloakLogin,
  SSO_VERIFIER_KEY,
  base64UrlEncode,
} from '../services/keycloak';

// ---------------------------------------------------------------------------
// base64UrlEncode unit tests
// ---------------------------------------------------------------------------
describe('base64UrlEncode', () => {
  it('encodes buffer to base64url without padding', () => {
    const buffer = new TextEncoder().encode('hello').buffer;
    const result = base64UrlEncode(buffer);
    expect(result).toBe('aGVsbG8');
    expect(result).not.toContain('=');
  });

  it('replaces + with - and / with _', () => {
    // Create bytes that produce + and / in standard base64
    const buffer = new Uint8Array([0xfa, 0xfe]).buffer;
    const result = base64UrlEncode(buffer);
    expect(result).not.toContain('+');
    expect(result).not.toContain('/');
    // Standard base64 of [0xFA, 0xFE] is "+v4=", base64url should be "-v4" (no padding)
    expect(result).toMatch(/^-/);
  });
});

// ---------------------------------------------------------------------------
// PKCE helpers
// ---------------------------------------------------------------------------
describe('generateCodeVerifier', () => {
  it('returns a string', () => {
    const verifier = generateCodeVerifier();
    expect(typeof verifier).toBe('string');
    expect(verifier.length).toBeGreaterThan(0);
  });

  it('returns base64url (no +, /, or = characters)', () => {
    const verifier = generateCodeVerifier();
    expect(verifier).not.toContain('+');
    expect(verifier).not.toContain('/');
    expect(verifier).not.toContain('=');
  });

  it('produces different values on successive calls', () => {
    const v1 = generateCodeVerifier();
    const v2 = generateCodeVerifier();
    expect(v1).not.toBe(v2);
  });

  it('is derived from 64 random bytes (length close to 86 for base64url of 64 bytes)', () => {
    const verifier = generateCodeVerifier();
    // 64 bytes → ceil(64*4/3) ≈ 86 chars but 64 bytes of random → exactly 86 chars base64url
    expect(verifier.length).toBe(86);
  });
});

describe('computeCodeChallenge', () => {
  it('returns a base64url string', async () => {
    const verifier = generateCodeVerifier();
    const challenge = await computeCodeChallenge(verifier);
    expect(typeof challenge).toBe('string');
    expect(challenge.length).toBeGreaterThan(0);
    expect(challenge).not.toContain('+');
    expect(challenge).not.toContain('/');
    expect(challenge).not.toContain('=');
  });

  it('returns consistent output for the same input', async () => {
    const verifier = 'test-verifier';
    const c1 = await computeCodeChallenge(verifier);
    const c2 = await computeCodeChallenge(verifier);
    expect(c1).toBe(c2);
  });

  it('produces different output for different verifiers', async () => {
    const c1 = await computeCodeChallenge('verifier-a');
    const c2 = await computeCodeChallenge('verifier-b');
    expect(c1).not.toBe(c2);
  });

  it('produces SHA-256 hash (43 chars for 32-byte output in base64url)', async () => {
    const challenge = await computeCodeChallenge('hello-pkce');
    // SHA-256 output is 32 bytes → base64url = 43 characters without padding
    expect(challenge.length).toBe(43);
  });
});

// ---------------------------------------------------------------------------
// redirectToKeycloakLogin
// ---------------------------------------------------------------------------
describe('redirectToKeycloakLogin', () => {
  let mockStorage: Record<string, string>;

  beforeEach(() => {
    mockStorage = {};
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

    // Mock window.location.href
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (window as any).location;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).location = { href: '', assign: vi.fn() };
  });

  it('stores the code_verifier in sessionStorage', async () => {
    try {
      await redirectToKeycloakLogin(
        'https://kc.example.com',
        'r',
        'c',
        'https://app.example.com/callback'
      );
    } catch {
      // Promise<never> — не должно выполняться после редиректа
    }

    expect(sessionStorage.setItem).toHaveBeenCalledWith(SSO_VERIFIER_KEY, expect.any(String));
    const storedValue = mockStorage[SSO_VERIFIER_KEY];
    expect(storedValue).toBeDefined();
    expect(storedValue!.length).toBeGreaterThan(0);
    expect(storedValue).not.toContain('=');
  });

  it('builds a URL with PKCE parameters', async () => {
    try {
      await redirectToKeycloakLogin(
        'https://kc.example.com',
        'r',
        'c',
        'https://app.example.com/sso/callback'
      );
    } catch {
      // ожидаемо
    }

    const { href } = window.location;
    expect(href).toContain('https://kc.example.com/realms/r/protocol/openid-connect/auth');

    const url = new URL(href);
    expect(url.searchParams.get('response_type')).toBe('code');
    expect(url.searchParams.get('client_id')).toBe('c');
    expect(url.searchParams.get('redirect_uri')).toBe('https://app.example.com/sso/callback');
    expect(url.searchParams.get('code_challenge_method')).toBe('S256');
    expect(url.searchParams.get('scope')).toBe('openid profile email');
    expect(url.searchParams.get('code_challenge')).toBeTruthy();
  });
});
