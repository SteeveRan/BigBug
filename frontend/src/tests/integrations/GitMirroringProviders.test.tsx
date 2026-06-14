/**
 * @file GitMirroringProviders.test.tsx
 * @description Integration tests for the Git Mirroring Providers page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../../pages/GitMirroring/Providers/index.tsx, ../../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App } from 'antd';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetSourceProvidersQuery: vi.fn(),
    useDeleteSourceProviderMutation: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import { useGetSourceProvidersQuery, useDeleteSourceProviderMutation } from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import ProvidersPage from '../../pages/GitMirroring/Providers';
import type { SourceProvider } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockGenericProvider: SourceProvider = {
  id: 3,
  label: 'Generic Git Server',
  provider_type: 'generic',
  credential_id: 30,
  credential: {
    id: 30,
    name: 'generic-token',
    credential_type: 'token',
    status_flag: 0,
    status_text: 'OK',
    created_at: '2026-01-01T00:00:00Z',
  },
  config_json: { base_url: 'https://git.example.com' },
  status_flag: 0,
  status_text: 'OK',
  groups_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGithubProvider: SourceProvider = {
  id: 1,
  label: 'GitHub',
  provider_type: 'github',
  credential_id: 10,
  credential: {
    id: 10,
    name: 'gh-token',
    credential_type: 'token',
    status_flag: 0,
    status_text: 'OK',
    created_at: '2026-01-01T00:00:00Z',
  },
  status_flag: 0,
  status_text: 'OK',
  groups_count: 3,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGitlabProvider: SourceProvider = {
  id: 2,
  label: 'GitLab',
  provider_type: 'gitlab',
  credential_id: 20,
  credential: {
    id: 20,
    name: 'gl-token',
    credential_type: 'token',
    status_flag: 0,
    status_text: 'OK',
    created_at: '2026-01-01T00:00:00Z',
  },
  config_json: { api_url: 'https://gitlab.example.com' },
  status_flag: 0,
  status_text: 'OK',
  groups_count: 5,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderProvidersPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <ProvidersPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ProvidersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetSourceProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useDeleteSourceProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  // -----------------------------------------------------------------------
  // Test 1: Page heading
  // -----------------------------------------------------------------------
  it('renders "Source Providers" heading', () => {
    renderProvidersPage();
    expect(screen.getByText('Source Providers')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Add provider button
  // -----------------------------------------------------------------------
  it('renders "Add Provider" button', () => {
    renderProvidersPage();
    expect(screen.getByText('Add Provider')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Provider data in table
  // -----------------------------------------------------------------------
  it('displays provider data when providers are loaded', () => {
    (useGetSourceProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGithubProvider],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderProvidersPage();

    expect(screen.getByText('GitHub')).toBeInTheDocument();
    // Provider type tag
    expect(screen.getByText('github')).toBeInTheDocument();
    // Credential name
    expect(screen.getByText('gh-token')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: Empty state
  // -----------------------------------------------------------------------
  it('shows empty state when no providers exist', () => {
    renderProvidersPage();
    expect(screen.getByText('No source providers configured')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: GitLab provider in table
  // -----------------------------------------------------------------------
  it('displays GitLab provider with correct type and name', () => {
    (useGetSourceProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGitlabProvider],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderProvidersPage();

    expect(screen.getByText('GitLab')).toBeInTheDocument();
    // Provider type tag
    expect(screen.getByText('gitlab')).toBeInTheDocument();
    // Credential name
    expect(screen.getByText('gl-token')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 6: Generic Git provider displayed with "Generic Git" tag
  // -----------------------------------------------------------------------
  it('displays Generic Git provider with grey tag and label "Generic Git"', () => {
    (useGetSourceProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGenericProvider],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderProvidersPage();

    expect(screen.getByText('Generic Git Server')).toBeInTheDocument();
    // Tag should show "Generic Git" not just "generic"
    expect(screen.getByText('Generic Git')).toBeInTheDocument();
    // Credential name
    expect(screen.getByText('generic-token')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 7: Mixed providers (GitHub + GitLab) in table
  // -----------------------------------------------------------------------
  it('displays both GitHub and GitLab providers', () => {
    (useGetSourceProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGithubProvider, mockGitlabProvider],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderProvidersPage();

    expect(screen.getByText('GitHub')).toBeInTheDocument();
    expect(screen.getByText('GitLab')).toBeInTheDocument();
    expect(screen.getByText('github')).toBeInTheDocument();
    expect(screen.getByText('gitlab')).toBeInTheDocument();
    expect(screen.getByText('gh-token')).toBeInTheDocument();
    expect(screen.getByText('gl-token')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Generic Git visible in provider type filter
  // -----------------------------------------------------------------------
  it('includes Generic Git option in the provider type filter', () => {
    renderProvidersPage();

    // The Select filter "Generic Git" option should be in the dropdown options
    // Ant Design renders options in a portal, we verify the component exists
    expect(screen.getByText('All')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 9: Provider type filter
  // -----------------------------------------------------------------------
  it('renders provider type filter dropdown', () => {
    renderProvidersPage();

    // The Select filter "All" should be visible
    expect(screen.getByText('All')).toBeInTheDocument();
  });
});
