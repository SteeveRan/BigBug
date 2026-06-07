/**
 * @file keycloak.ts
 * @description PKCE utilities for the Authorization Code + PKCE (S256) flow
 *              against the Keycloak *public* frontend client.
 *
 *              WHY no Keycloak-js singleton: keycloak-js does not expose
 *              authServerUrl/realm/clientId as readable properties until after
 *              init() is called (which triggers a full OIDC discovery round-trip
 *              and tries to restore an existing session). We only need to build
 *              the authorization URL, so we do it directly from the config
 *              returned by the backend /auth/sso/config endpoint.
 *
 * @relatedFiles ../hooks/useKeycloakAuth.ts, ../store/authSlice.ts
 */

// ---------------------------------------------------------------------------
// PKCE helpers
// ---------------------------------------------------------------------------

export function base64UrlEncode(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

export function generateCodeVerifier(): string {
  const array = new Uint8Array(64);
  crypto.getRandomValues(array);
  return base64UrlEncode(array.buffer);
}

export async function computeCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return base64UrlEncode(hash);
}

// ---------------------------------------------------------------------------
// Public helpers
// ---------------------------------------------------------------------------

/** sessionStorage key used to persist the code_verifier across the redirect. */
export const SSO_VERIFIER_KEY = 'sso_code_verifier';

/**
 * Kick off the Authorization Code + PKCE flow by redirecting the browser to
 * Keycloak's authorization endpoint.
 *
 * We build the URL directly from the SSO config returned by the backend
 * (/auth/sso/config) instead of relying on keycloak-js instance properties,
 * because keycloak-js does not expose authServerUrl/realm/clientId as readable
 * properties until after init() is called.
 *
 * Stores the generated code_verifier in sessionStorage so
 * `useKeycloakAuth.handleCallback` can retrieve it after the redirect.
 */
export async function redirectToKeycloakLogin(
  url: string,
  realm: string,
  clientId: string,
  redirectUri: string
): Promise<never> {
  const verifier = generateCodeVerifier();
  sessionStorage.setItem(SSO_VERIFIER_KEY, verifier);

  const challenge = await computeCodeChallenge(verifier);

  const params = new URLSearchParams();
  params.set('response_type', 'code');
  params.set('client_id', clientId);
  params.set('redirect_uri', redirectUri);
  params.set('code_challenge', challenge);
  params.set('code_challenge_method', 'S256');
  params.set('scope', 'openid profile email');

  const loginUrl = `${url}/realms/${realm}/protocol/openid-connect/auth?${params.toString()}`;

  window.location.href = loginUrl;
  // Unreachable — the browser navigation replaces the current page.
  return undefined as never;
}
