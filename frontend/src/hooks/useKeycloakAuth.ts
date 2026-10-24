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

import { useEffect, useState, useCallback } from 'react';
import { useGetSsoConfigQuery } from '../store/api';
import { redirectToKeycloakLogin, SSO_VERIFIER_KEY, SSO_PROVIDER_KEY } from '../services/keycloak';
import type { SSOProviderPublic } from '../types';

/** Redirect URI the Keycloak public client is configured to accept. */
const SSO_REDIRECT_URI = `${window.location.origin}/sso/callback`;

interface SsoState {
  /** Whether the SSO config has been fetched and processed. */
  ready: boolean;
  /** `true` when the backend reports SSO is enabled and at least one provider is available. */
  enabled: boolean;
  /** Enabled providers to render one button each. */
  providers: SSOProviderPublic[];
  /** Any error that occurred during initialisation. */
  error: string | null;
}

/**
 * Thin wrapper around the SSO bootstrap.
 *
 * Usage (once per app, e.g. in App or Login):
 * ```ts
 * const { ready, enabled, providers, login, handleCallback } = useKeycloakAuth()
 * ```
 */
export function useKeycloakAuth() {
  // NOTE: we call the query unconditionally — RTK Query deduplicates it.
  const { data: config, isLoading, isError, error } = useGetSsoConfigQuery();

  const [state, setState] = useState<SsoState>({
    ready: false,
    enabled: false,
    providers: [],
    error: null,
  });

  useEffect(() => {
    if (isLoading) return;

    // API error or config not available → treat as disabled.
    if (isError || !config || !config.enabled || config.providers.length === 0) {
      setState({ ready: true, enabled: false, providers: [], error: null });
      return;
    }

    setState({
      ready: true,
      enabled: true,
      providers: config.providers,
      error: null,
    });
  }, [isLoading, isError, config, error]);

  /** Start the PKCE redirect for a specific provider. */
  const login = useCallback(async (provider: SSOProviderPublic) => {
    if (!provider) {
      console.error('[useKeycloakAuth] login() called but no provider given');
      return;
    }
    await redirectToKeycloakLogin(
      provider.url,
      provider.realm,
      provider.client_id,
      SSO_REDIRECT_URI,
      provider.id
    );
  }, []);

  /**
   * After the Keycloak redirect the browser lands on /sso/callback with
   * `?code=...&state=<provider_id>`.  This helper reads the code, verifier and
   * provider_id and returns the payload for POST /auth/oidc/exchange.
   */
  const handleCallback = useCallback(():
    | {
        code: string;
        redirect_uri: string;
        code_verifier: string;
        provider_id: number;
        state: string;
      }
    | { error: string } => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const errorParam = params.get('error');

    if (errorParam) {
      const desc = params.get('error_description') || errorParam;
      return { error: desc };
    }

    if (!code) {
      return { error: 'Authorization code missing from callback URL' };
    }

    const verifier = sessionStorage.getItem(SSO_VERIFIER_KEY);
    if (!verifier) {
      return { error: 'PKCE code_verifier not found in sessionStorage — possible stale callback' };
    }

    const providerIdRaw = params.get('state') ?? sessionStorage.getItem(SSO_PROVIDER_KEY);
    const providerId = providerIdRaw !== null ? Number(providerIdRaw) : NaN;
    if (!Number.isInteger(providerId)) {
      return { error: 'provider_id missing from SSO callback state' };
    }

    return {
      code,
      redirect_uri: SSO_REDIRECT_URI,
      code_verifier: verifier,
      provider_id: providerId,
      state: providerIdRaw!,
    };
  }, []);

  return {
    ready: state.ready,
    enabled: state.enabled,
    providers: state.providers,
    error: state.error,
    login,
    handleCallback,
  };
}
