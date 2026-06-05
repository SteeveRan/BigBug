/**
 * @file keycloak.ts
 * @description Singleton Keycloak-js instance and PKCE utilities for the
 *              Authorization Code + PKCE (S256) flow against the Keycloak
 *              *public* frontend client.
 *
 * @dependencies keycloak-js ^24
 * @relatedFiles ../hooks/useKeycloakAuth.ts, ../store/authSlice.ts
 */

import Keycloak from 'keycloak-js'

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

let _instance: Keycloak | null = null

/**
 * Return (or lazily create) the single Keycloak-js instance.
 *
 * The instance is configured as a *public* client — no secret — and uses the
 * standard Authorization Code + PKCE flow.
 */
export function getKeycloakInstance(
  url: string,
  realm: string,
  clientId: string,
): Keycloak {
  if (_instance) return _instance
  _instance = new Keycloak({ url, realm, clientId })
  return _instance
}

/** Reset the singleton — only intended for tests. */
export function resetKeycloakInstance(): void {
  _instance = null
}

// ---------------------------------------------------------------------------
// PKCE helpers
// ---------------------------------------------------------------------------

function base64UrlEncode(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

function generateCodeVerifier(): string {
  const array = new Uint8Array(64)
  crypto.getRandomValues(array)
  return base64UrlEncode(array.buffer)
}

async function computeCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(verifier)
  const hash = await crypto.subtle.digest('SHA-256', data)
  return base64UrlEncode(hash)
}

// ---------------------------------------------------------------------------
// Public helpers
// ---------------------------------------------------------------------------

/** sessionStorage key used to persist the code_verifier across the redirect. */
export const SSO_VERIFIER_KEY = 'sso_code_verifier'

/**
 * Kick off the Authorization Code + PKCE flow by redirecting the browser to
 * Keycloak's authorization endpoint.
 *
 * We construct the URL manually because keycloak-js 24.x does not expose
 * `codeChallenge` via its public types, and we need the code_verifier to be
 * sent to *our* backend rather than consumed inside the adapter.
 *
 * Stores the generated code_verifier in sessionStorage so
 * `useKeycloakAuth.handleCallback` can retrieve it after the redirect.
 */
export async function redirectToKeycloakLogin(
  keycloak: Keycloak,
  redirectUri: string,
): Promise<never> {
  const verifier = generateCodeVerifier()
  sessionStorage.setItem(SSO_VERIFIER_KEY, verifier)

  const challenge = await computeCodeChallenge(verifier)

  // authServerUrl is a public property on the Keycloak instance.
  const baseUrl = keycloak.authServerUrl as string
  const realm = keycloak.realm
  const clientId = keycloak.clientId as string | undefined

  const params = new URLSearchParams()
  params.set('response_type', 'code')
  params.set('client_id', clientId ?? '')
  params.set('redirect_uri', redirectUri)
  params.set('code_challenge', challenge)
  params.set('code_challenge_method', 'S256')
  params.set('scope', 'openid profile email')

  const loginUrl = `${baseUrl}/realms/${realm}/protocol/openid-connect/auth?${params.toString()}`

  window.location.href = loginUrl
  // Unreachable — the browser navigation replaces the current page.
  return undefined as never
}
