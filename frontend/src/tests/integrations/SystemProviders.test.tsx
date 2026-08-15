/**
 * @file SystemProviders.test.tsx
 * @description Integration tests for the admin System Providers page
 *              (`/admin/providers`). Verifies system providers are loaded and
 *              rendered, and that the error/empty states work.
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App } from 'antd';

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetProviderTypesQuery: vi.fn(),
    useGetProvidersQuery: vi.fn(),
    useUpdateProviderMutation: vi.fn(),
    useTestProviderMutation: vi.fn(),
    useListUsersQuery: vi.fn(),
    useGetCredentialsQuery: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

import { api } from '../../store/api';
import {
  useGetProviderTypesQuery,
  useGetProvidersQuery,
  useUpdateProviderMutation,
  useTestProviderMutation,
  useListUsersQuery,
  useGetCredentialsQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import SystemProvidersPage from '../../pages/Admin/SystemProviders';
import type { ResourceProvider, ProviderTypeSpec } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function mockProvider(overrides: Partial<ResourceProvider> = {}): ResourceProvider {
  return {
    id: 1,
    domain: 'git',
    subtype: 'gitlab',
    category: 'system',
    direction: 'internal',
    name: 'system-gitlab',
    label: 'System GitLab',
    description: null,
    base_url: 'https://gitlab.internal',
    config: {},
    credential_id: null,
    owner_user_id: null,
    visibility: 'owner',
    team_id: null,
    team_name: null,
    is_active: true,
    is_default: true,
    is_protected: true,
    verify_ssl: true,
    priority: 0,
    status_flag: 0,
    status_text: 'OK',
    last_checked_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    has_credential: false,
    ...overrides,
  };
}

const mockType: ProviderTypeSpec = {
  subtype: 'gitlab',
  domain: 'git',
  label: 'GitLab',
  capabilities: [],
  allowed_categories: ['system'],
  allowed_directions: ['internal'],
  allowed_credential_types: ['gitlab_token'],
  config_schema: { type: 'object', properties: {}, additionalProperties: false },
  oci_compliant: false,
  requires_base_url: true,
};

describe('SystemProvidersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: () => true,
      hasAnyPermission: () => true,
      hasAllPermissions: () => true,
      permissions: [],
    });
    (useGetProviderTypesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockType],
      isLoading: false,
      isError: false,
    });
    (useUpdateProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
    (useTestProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: { ok: true, status_flag: 0, status_text: 'OK' } }),
      { isLoading: false },
    ]);
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    (useGetCredentialsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
  });

  it('renders System Providers heading and refresh button', () => {
    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(
      <Provider store={createTestStore()}>
        <BrowserRouter>
          <App>
            <SystemProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
    expect(screen.getAllByText('System Providers').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Refresh')).toBeInTheDocument();
  });

  it('renders system provider rows', () => {
    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockProvider({ id: 1, label: 'System GitLab', is_protected: true })],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(
      <Provider store={createTestStore()}>
        <BrowserRouter>
          <App>
            <SystemProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
    expect(screen.getByText('System GitLab')).toBeInTheDocument();
    expect(screen.getByText('GitLab')).toBeInTheDocument();
  });

  it('renders default (non-system) providers alongside system providers', () => {
    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [
        mockProvider({ id: 1, label: 'System GitLab', category: 'system', is_default: false }),
        mockProvider({
          id: 2,
          domain: 'git',
          subtype: 'github',
          category: 'public',
          direction: 'external',
          name: 'github-anonymous',
          label: 'GitHub Anonymous',
          is_default: true,
          is_protected: true,
        }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(
      <Provider store={createTestStore()}>
        <BrowserRouter>
          <App>
            <SystemProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
    expect(screen.getByText('System GitLab')).toBeInTheDocument();
    expect(screen.getByText('GitHub Anonymous')).toBeInTheDocument();
    expect(screen.getByText('Public')).toBeInTheDocument();
  });

  it('hides ordinary public/private (non-default, non-system) providers', () => {
    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [
        mockProvider({
          id: 3,
          domain: 'git',
          subtype: 'github',
          category: 'public',
          direction: 'external',
          name: 'ordinary-public',
          label: 'Ordinary Public',
          is_default: false,
          is_protected: false,
        }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(
      <Provider store={createTestStore()}>
        <BrowserRouter>
          <App>
            <SystemProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
    expect(screen.queryByText('Ordinary Public')).not.toBeInTheDocument();
  });

  it('shows error alert when providers fail to load', () => {
    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: true,
      refetch: vi.fn(),
    });
    render(
      <Provider store={createTestStore()}>
        <BrowserRouter>
          <App>
            <SystemProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
    expect(screen.getByText('Failed to load providers')).toBeInTheDocument();
  });
});
