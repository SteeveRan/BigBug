/**
 * @file SsoCallback/index.tsx
 * @description Handles the browser redirect from Keycloak's authorization
 *              endpoint. Extracts the authorization code, POSTs it to the
 *              backend OIDC exchange, and stores the resulting app tokens.
 *
 * @dependencies ../hooks/useKeycloakAuth, ../store/api, ../store/authSlice
 * @relatedFiles ../Login/index.tsx, ../../router/index.tsx
 */

import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { Typography, Spin, Alert, Flex } from 'antd';
import { useKeycloakAuth } from '../../hooks/useKeycloakAuth';
import { useSsoExchangeMutation } from '../../store/api';
import { useAppDispatch } from '../../store';
import { setCredentials } from '../../store/authSlice';

const { Text, Link } = Typography;

export function SsoCallbackPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { handleCallback } = useKeycloakAuth();
  const [exchange] = useSsoExchangeMutation();
  const called = useRef(false);
  const [fallbackError, setFallbackError] = useState<string | null>(null);

  useEffect(() => {
    // React StrictMode double-mounts in dev — guard against double exchange.
    if (called.current) return;
    called.current = true;

    const payload = handleCallback();
    if ('error' in payload) {
      setFallbackError(payload.error);
      navigate(`/login?error=${encodeURIComponent(payload.error)}`, { replace: true });
      return;
    }

    exchange(payload)
      .unwrap()
      .then(async (result) => {
        // Fetch the user profile using the access token.
        const meResponse = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${result.access_token}` },
        });
        const me = await meResponse.json();

        dispatch(
          setCredentials({
            accessToken: result.access_token,
            refreshToken: result.refresh_token,
            user: me,
          })
        );
        navigate('/', { replace: true });
      })
      .catch((err) => {
        const detail = (err as { data?: { detail?: string } })?.data?.detail || 'SSO login failed';
        setFallbackError(detail);
        navigate(`/login?error=${encodeURIComponent(detail)}`, { replace: true });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // If navigation didn't happen (e.g. blocked), show a fallback error UI.
  if (fallbackError) {
    return (
      <Flex vertical align="center" justify="center" style={{ minHeight: '100vh' }} gap="middle">
        <Alert type="error" title="SSO Login Failed" description={fallbackError} showIcon />
        <Link onClick={() => navigate('/login')}>Back to login</Link>
      </Flex>
    );
  }

  return (
    <Flex vertical align="center" justify="center" style={{ minHeight: '100vh' }} gap="middle">
      <Spin size="large" />
      <Text type="secondary">Completing sign in…</Text>
    </Flex>
  );
}
