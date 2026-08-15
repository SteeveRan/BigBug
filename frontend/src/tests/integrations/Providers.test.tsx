/**
 * @file Providers.test.tsx
 * @description Integration tests for the unified Providers page (`/settings/providers`).
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
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import ProvidersPage from '../../pages/Settings/Providers';
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
    subtype: 'github',
    category: 'private',
    direction: 'external',
    name: 'github-main',
    label: 'GitHub',
    description: null,
    base_url: null,
    config: {},
    credential_id: null,
    owner_user_id: 1,
    visibility: 'owner',
    team_id: null,
    team_name: null,
    is_active: true,
    is_default: false,
    is_protected: false,
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
  subtype: 'github',
  domain: 'git',
  label: 'GitHub',
  capabilities: [],
  allowed_categories: ['public', 'private'],
  allowed_directions: ['external'],
  allowed_credential_types: ['github_token'],
  config_schema: { type: 'object', properties: {}, additionalProperties: false },
  oci_compliant: false,
  requires_base_url: false,
};

describe('ProvidersPage', () => {
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
  });

  it('renders Providers heading and Create button', () => {
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
            <ProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
    expect(screen.getAllByText('Providers').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Create provider')).toBeInTheDocument();
  });

  it('renders provider rows with System/Public/Private badges', () => {
    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [
        mockProvider({ id: 1, label: 'System GitLab', category: 'system', is_protected: true }),
        mockProvider({ id: 2, label: 'Public Hub', category: 'public' }),
        mockProvider({ id: 3, label: 'Private Git', category: 'private' }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(
      <Provider store={createTestStore()}>
        <BrowserRouter>
          <App>
            <ProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
    expect(screen.getByText('System GitLab')).toBeInTheDocument();
    expect(screen.getByText('Public Hub')).toBeInTheDocument();
    expect(screen.getByText('Private Git')).toBeInTheDocument();
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
            <ProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
    expect(screen.getByText('Failed to load providers')).toBeInTheDocument();
  });
});
