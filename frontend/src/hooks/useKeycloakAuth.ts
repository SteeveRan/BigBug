/**
 * @file useKeycloakAuth.ts
 * @description React hook that fetches SSO config from the backend and exposes
 *              ergonomic `login()` / `handleCallback()` helpers.
 *
 *              During development / local-only deployments the hook stays idle
 *              so the pure-local login form works unchanged.
 *
 * @dependencies ../services/keycloak.ts, ../store/api.ts (for getSsoConfig)
 * @relatedFiles ../pages/Login/index.tsx, ../pages/SsoCallback/index.tsx
 */

import { useEffect, useState, useCallback } from 'react'
import { useGetSsoConfigQuery } from '../store/api'
import {
  redirectToKeycloakLogin,
  SSO_VERIFIER_KEY,
} from '../services/keycloak'

/** Redirect URI the Keycloak public client is configured to accept. */
const SSO_REDIRECT_URI = `${window.location.origin}/sso/callback`

interface SsoState {
  /** Whether the SSO config has been fetched and processed. */
  ready: boolean
  /** `true` when the backend reports SSO is enabled. */
  enabled: boolean
  /** SSO configuration (url, realm, clientId) */
  config: { url: string; realm: string; client_id: string } | null
  /** Any error that occurred during initialisation. */
  error: string | null
}

/**
 * Thin wrapper around the SSO bootstrap.
 *
 * Usage (once per app, e.g. in App or Login):
 * ```ts
 * const { ready, enabled, login, handleCallback } = useKeycloakAuth()
 * ```
 */
export function useKeycloakAuth() {
  // NOTE: we call the query unconditionally — RTK Query deduplicates it.
  const { data: config, isLoading, isError, error } = useGetSsoConfigQuery()

  const [state, setState] = useState<SsoState>({
    ready: false,
    enabled: false,
    config: null,
    error: null,
  })

  useEffect(() => {
    if (isLoading) return

    // API error or config not available → treat as disabled.
    if (isError || !config || !config.enabled) {
      setState({ ready: true, enabled: false, config: null, error: null })
      return
    }

    setState({
      ready: true,
      enabled: true,
      config: { url: config.url, realm: config.realm, client_id: config.client_id },
      error: null,
    })
  }, [isLoading, isError, config, error])

  /** Start the PKCE redirect. */
  const login = useCallback(async () => {
    if (!state.config) {
      console.error('[useKeycloakAuth] login() called but SSO config not available')
      return
    }
    await redirectToKeycloakLogin(
      state.config.url,
      state.config.realm,
      state.config.client_id,
      SSO_REDIRECT_URI
    )
  }, [state.config])

  /**
   * After the Keycloak redirect the browser lands on /sso/callback with
   * `?code=...&session_state=...`.  This helper reads the code and stored
   * verifier and returns the payload for POST /auth/oidc/exchange.
   */
  const handleCallback = useCallback(():
    | { code: string; redirect_uri: string; code_verifier: string }
    | { error: string } => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const errorParam = params.get('error')

    if (errorParam) {
      const desc = params.get('error_description') || errorParam
      return { error: desc }
    }

    if (!code) {
      return { error: 'Authorization code missing from callback URL' }
    }

    const verifier = sessionStorage.getItem(SSO_VERIFIER_KEY)
    if (!verifier) {
      return { error: 'PKCE code_verifier not found in sessionStorage — possible stale callback' }
    }

    return { code, redirect_uri: SSO_REDIRECT_URI, code_verifier: verifier }
  }, [])

  return {
    ready: state.ready,
    enabled: state.enabled,
    error: state.error,
    login,
    handleCallback,
  }
}
