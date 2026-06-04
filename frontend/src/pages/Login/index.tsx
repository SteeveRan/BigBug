import { useState } from 'react'
import { useNavigate } from 'react-router'
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material'
import { useAppDispatch } from '../../store'
import { setCredentials } from '../../store/authSlice'
import { useLoginMutation, useGetMeQuery } from '../../store/api'

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [login, { isLoading }] = useLoginMutation()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const result = await login({ username, password }).unwrap()
      // Fetch user info
      const meResponse = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${result.access_token}` },
      })
      const me = await meResponse.json()
      dispatch(
        setCredentials({
          accessToken: result.access_token,
          refreshToken: result.refresh_token,
          user: me,
        })
      )
      navigate('/')
    } catch {
      setError('Invalid username or password')
    }
  }

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
        </CardContent>
      </Card>
    </Box>
  )
}
