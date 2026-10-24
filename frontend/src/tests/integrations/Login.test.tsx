/**
 * @file Login.test.tsx
 * @description Integration tests for the Login page SSO section:
 *              one button per enabled provider, provider order,
 *              hidden entirely when SSO is disabled or the list is empty.
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, antd
 * @relatedFiles ../pages/Login/index.tsx, ../hooks/useKeycloakAuth.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App as AntApp } from 'antd';

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useLoginMutation: () => [vi.fn(), { isLoading: false }],
    useGetSsoConfigQuery: vi.fn(),
  };
});

import { api } from '../../store/api';
import { LoginPage } from '../../pages/Login';

// Mock useKeycloakAuth — Login consumes the hook, not the query directly.
const mockUseKeycloakAuth = vi.fn();
vi.mock('../../hooks/useKeycloakAuth', () => ({
  useKeycloakAuth: () => mockUseKeycloakAuth(),
}));

// Avoid the real redirect (window.location.href assignment is a no-op stub in jsdom)
vi.mock('../../services/keycloak', () => ({
  redirectToKeycloakLogin: vi.fn().mockResolvedValue(undefined),
  SSO_VERIFIER_KEY: 'sso_code_verifier',
  SSO_PROVIDER_KEY: 'sso_provider_id',
  buildState: (id: number) => String(id),
}));

const providerA = {
  id: 1,
  name: 'Corporate',
  url: 'https://a.example.com',
  realm: 'r1',
  client_id: 'c1',
};
const providerB = {
  id: 2,
  name: 'Partner',
  url: 'https://b.example.com',
  realm: 'r2',
  client_id: 'c2',
};

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(api.middleware),
  });
}

function renderLoginPage() {
  const store = createTestStore();
  render(
    <Provider store={store}>
      <BrowserRouter>
        <AntApp>
          <LoginPage />
        </AntApp>
      </BrowserRouter>
    </Provider>
  );
  return store;
}

describe('LoginPage SSO buttons', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseKeycloakAuth.mockReturnValue({
      ready: true,
      enabled: false,
      providers: [],
      error: null,
      login: vi.fn(),
      handleCallback: vi.fn(),
    });
  });

  it('renders one SSO button per enabled provider, in provider order', () => {
    mockUseKeycloakAuth.mockReturnValue({
      ready: true,
      enabled: true,
      providers: [providerA, providerB],
      error: null,
      login: vi.fn(),
      handleCallback: vi.fn(),
    });

    renderLoginPage();

    const buttons = screen
      .getAllByRole('button')
      .filter((b) => b.textContent?.startsWith('Sign in with'));
    expect(buttons.map((b) => b.textContent)).toEqual([
      'Sign in with Corporate',
      'Sign in with Partner',
    ]);
  });

  it('renders no SSO UI when enabled=false (master switch)', () => {
    mockUseKeycloakAuth.mockReturnValue({
      ready: true,
      enabled: false,
      providers: [providerA],
      error: null,
      login: vi.fn(),
      handleCallback: vi.fn(),
    });

    renderLoginPage();

    expect(screen.queryByText(/Sign in with/)).not.toBeInTheDocument();
  });

  it('renders no SSO UI when the provider list is empty', () => {
    mockUseKeycloakAuth.mockReturnValue({
      ready: true,
      enabled: true,
      providers: [],
      error: null,
      login: vi.fn(),
      handleCallback: vi.fn(),
    });

    renderLoginPage();

    expect(screen.queryByText(/Sign in with/)).not.toBeInTheDocument();
  });

  it('calls login() with the clicked provider', () => {
    const loginMock = vi.fn();
    mockUseKeycloakAuth.mockReturnValue({
      ready: true,
      enabled: true,
      providers: [providerA, providerB],
      error: null,
      login: loginMock,
      handleCallback: vi.fn(),
    });

    renderLoginPage();

    fireEvent.click(screen.getByText('Sign in with Partner'));
    expect(loginMock).toHaveBeenCalledWith(providerB);
  });
});
