import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Divider,
} from '@mui/material';
import { useAppDispatch } from '../../store';
import { setCredentials } from '../../store/authSlice';
import { useLoginMutation } from '../../store/api';
import { useKeycloakAuth } from '../../hooks/useKeycloakAuth';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [login, { isLoading }] = useLoginMutation();
  const { ready, enabled, login: ssoLogin } = useKeycloakAuth();

  // Propagate error query param from SSO callback failures.
  useEffect(() => {
    const param = searchParams.get('error');
    if (param) {
      setError(param);
      // Clean up the URL so the message doesn't survive a refresh.
      navigate('/login', { replace: true });
    }
  }, [searchParams, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const result = await login({ username, password }).unwrap();
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
      navigate('/');
    } catch {
      setError('Invalid username or password');
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
      }}
    >
      <Card sx={{ width: 400, p: 2 }}>
        <CardContent>
          <Typography variant="h4" fontWeight="bold" color="primary" gutterBottom>
            BigBug
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            DevOps Sync & Build Service
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit}>
            <TextField
              label="Username"
              fullWidth
              margin="normal"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
            <TextField
              label="Password"
              type="password"
              fullWidth
              margin="normal"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              sx={{ mt: 2 }}
              disabled={isLoading}
            >
              {isLoading ? <CircularProgress size={24} /> : 'Sign In'}
            </Button>
          </Box>

          {/* SSO button — shown only when the backend reports SSO is enabled
              and the config has finished loading. */}
          {ready && enabled && (
            <>
              <Divider sx={{ my: 2 }}>or</Divider>
              <Button variant="outlined" fullWidth size="large" onClick={ssoLogin}>
                Sign in with SSO
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
