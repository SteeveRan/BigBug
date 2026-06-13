/**
 * @file GitMirroringMirrors.test.tsx
 * @description Integration tests for the Git Mirroring Mirrors page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../../pages/GitMirroring/Mirrors/index.tsx, ../../../store/api.ts
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
    useGetMirrorsQuery: vi.fn(),
    useDeleteMirrorV2Mutation: vi.fn(),
    useTriggerMirrorSyncMutation: vi.fn(),
    useTriggerFreshnessCheckMutation: vi.fn(),
    useGetSourceRepositoriesQuery: vi.fn(),
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
  useGetMirrorsQuery,
  useDeleteMirrorV2Mutation,
  useTriggerMirrorSyncMutation,
  useTriggerFreshnessCheckMutation,
  useGetSourceRepositoriesQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import MirrorsPage from '../../pages/GitMirroring/Mirrors';
import type { Mirror } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockMirror: Mirror = {
  id: 1,
  source_repository_id: 10,
  source_repository: {
    id: 10,
    full_name: 'owner/test-repo',
    description: 'A test repository',
    name: 'test-repo',
    html_url: 'https://github.com/owner/test-repo',
    clone_url: 'https://github.com/owner/test-repo.git',
    default_branch: 'main',
    source_group_id: 1,
    external_id: 'test-repo-ext',
    discovery_status: 0,
    discovery_status_text: 'OK',
    has_readme: false,
    archived: false,
    fork: false,
    private: false,
    stars: 5,
    forks: 2,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  target_namespace: 'gitlab-ns',
  target_project_name: 'test-repo',
  target_path: 'gitlab-ns/test-repo',
  sync_group_id: 5,
  sync_group_name: 'default',
  target_gitlab_name: 'gitlab-local',
  status_flag: 0,
  status_text: 'OK',
  discovery_status: 0,
  discovery_status_text: 'OK',
  last_sync_at: '2026-06-07T12:00:00Z',
  last_freshness_check_at: '2026-06-07T12:30:00Z',
  is_active: true,
  is_imported: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-07T12:00:00Z',
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderMirrorsPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <MirrorsPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('MirrorsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useDeleteMirrorV2Mutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useTriggerMirrorSyncMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useTriggerFreshnessCheckMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useGetSourceRepositoriesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  // -----------------------------------------------------------------------
  // Test 1: Page heading
  // -----------------------------------------------------------------------
  it('renders "Mirrors" heading', () => {
    renderMirrorsPage();
    expect(screen.getByText('Mirrors')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Create and Import buttons
  // -----------------------------------------------------------------------
  it('renders "Create Mirror" and "Import Existing Mirror" buttons', () => {
    renderMirrorsPage();
    expect(screen.getByText('Create Mirror')).toBeInTheDocument();
    expect(screen.getByText('Import Existing Mirror')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Search field and status filter
  // -----------------------------------------------------------------------
  it('renders search input and status filter', () => {
    renderMirrorsPage();

    expect(screen.getByPlaceholderText(/Search by source URL/)).toBeInTheDocument();
    // Status filter Select is present (defaults to "All")
    expect(screen.getByText('All')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: Table with mirror data
  // -----------------------------------------------------------------------
  it('displays mirror data in the table', () => {
    (useGetMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockMirror],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderMirrorsPage();

    expect(screen.getByText('owner/test-repo')).toBeInTheDocument();
    expect(screen.getByText('gitlab-ns/test-repo')).toBeInTheDocument();
    expect(screen.getByText('OK')).toBeInTheDocument();
    expect(screen.getByText('default')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Empty state
  // -----------------------------------------------------------------------
  it('shows empty state when no mirrors exist', () => {
    renderMirrorsPage();
    expect(screen.getByText('No mirrors found')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 6: Loading spinner
  // -----------------------------------------------------------------------
  it('shows loading spinner when data is loading', () => {
    (useGetMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    const { container } = renderMirrorsPage();
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 7: Error alert on fetch failure
  // -----------------------------------------------------------------------
  it('shows error alert when fetch fails', () => {
    (useGetMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
    });

    renderMirrorsPage();
    expect(screen.getByText('Failed to load mirrors')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Smoke test
  // -----------------------------------------------------------------------
  it('renders without crashing (smoke test)', () => {
    const { container } = renderMirrorsPage();
    expect(container).toBeTruthy();
  });
});
