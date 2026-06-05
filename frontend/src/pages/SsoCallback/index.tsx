/**
 * @file SsoCallback/index.tsx
 * @description Handles the browser redirect from Keycloak's authorization
 *              endpoint. Extracts the authorization code, POSTs it to the
 *              backend OIDC exchange, and stores the resulting app tokens.
 *
 * @dependencies ../hooks/useKeycloakAuth, ../store/api, ../store/authSlice
 * @relatedFiles ../Login/index.tsx, ../../router/index.tsx
 */

import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { Box, Typography, CircularProgress } from '@mui/material'
import { useKeycloakAuth } from '../../hooks/useKeycloakAuth'
import { useSsoExchangeMutation } from '../../store/api'
import { useAppDispatch } from '../../store'
import { setCredentials } from '../../store/authSlice'

export function SsoCallbackPage() {
  const navigate = useNavigate()
  const dispatch = useAppDispatch()
  const { handleCallback } = useKeycloakAuth()
  const [exchange] = useSsoExchangeMutation()
  const called = useRef(false)

  useEffect(() => {
    // React StrictMode double-mounts in dev — guard against double exchange.
    if (called.current) return
    called.current = true

    const payload = handleCallback()
    if ('error' in payload) {
      // Navigate to login with the error description.
      navigate(`/login?error=${encodeURIComponent(payload.error)}`, { replace: true })
      return
    }

    exchange(payload)
      .unwrap()
      .then(async (result) => {
        // Fetch the user profile using the access token.
        const meResponse = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${result.access_token}` },
        })
        const me = await meResponse.json()

        dispatch(
          setCredentials({
            accessToken: result.access_token,
            refreshToken: result.refresh_token,
            user: me,
          }),
        )
        navigate('/', { replace: true })
      })
      .catch((err) => {
        const detail =
          (err as { data?: { detail?: string } })?.data?.detail ||
          'SSO login failed'
        navigate(`/login?error=${encodeURIComponent(detail)}`, { replace: true })
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        bgcolor: 'background.default',
      }}
    >
      <CircularProgress />
      <Typography variant="body1" color="text.secondary">
        Completing sign in…
      </Typography>
    </Box>
  )
}
