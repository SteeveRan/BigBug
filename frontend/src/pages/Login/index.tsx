import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Card, Input, Button, Typography, Divider, Flex, App } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { useAppDispatch } from '../../store';
import { setCredentials } from '../../store/authSlice';
import { useLoginMutation } from '../../store/api';
import { useKeycloakAuth } from '../../hooks/useKeycloakAuth';

const { Title, Text } = Typography;

export function LoginPage() {
  const { message } = App.useApp();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [login, { isLoading }] = useLoginMutation();
  const { ready, enabled, login: ssoLogin } = useKeycloakAuth();

  // Propagate error query param from SSO callback failures.
  useEffect(() => {
    const param = searchParams.get('error');
    if (param) {
      message.error(param);
      // Clean up the URL so the message doesn't survive a refresh.
      navigate('/login', { replace: true });
    }
  }, [searchParams, navigate, message]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
      message.error('Invalid username or password');
    }
  };

  return (
    <Flex
      vertical
      align="center"
      justify="center"
      style={{ minHeight: '100vh', padding: 16 }}
    >
      <Card style={{ width: '100%', maxWidth: 400 }}>
        <Flex vertical gap="middle">
          <div>
            <Title level={3} style={{ marginBottom: 0 }}>
              BigBug
            </Title>
            <Text type="secondary">DevOps Sync & Build Service</Text>
          </div>

          <form onSubmit={handleSubmit}>
            <Flex vertical gap="middle">
              <Input
                prefix={<UserOutlined />}
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
                size="large"
              />
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                size="large"
              />
              <Button
                type="primary"
                htmlType="submit"
                block
                size="large"
                loading={isLoading}
              >
                Sign In
              </Button>
            </Flex>
          </form>

          {/* SSO button — shown only when the backend reports SSO is enabled
              and the config has finished loading. */}
          {ready && enabled && (
            <>
              <Divider>or</Divider>
              <Button block size="large" onClick={ssoLogin}>
                Sign in with SSO
              </Button>
            </>
          )}
        </Flex>
      </Card>
      <Text type="secondary" style={{ marginTop: 16, fontSize: 12 }}>
        BigBug Platform
      </Text>
    </Flex>
  );
}
