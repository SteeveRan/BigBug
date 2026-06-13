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
import {
  useGetSourceProvidersQuery,
  useDeleteSourceProviderMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import ProvidersPage from '../../pages/GitMirroring/Providers';
import type { SourceProvider } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockProvider: SourceProvider = {
  id: 1,
  name: 'GitHub',
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
      data: [mockProvider],
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
});
