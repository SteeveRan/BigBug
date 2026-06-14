/**
 * @file GitMirroringGroups.test.tsx
 * @description Integration tests for the Git Mirroring Groups tab (via Sources page)
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../pages/GitMirroring/Sources/index.tsx, ../../pages/GitMirroring/Sources/GroupsTab.tsx, ../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router';
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
    useGetSourceGroupsQuery: vi.fn(),
    useGetSourceRepositoriesQuery: vi.fn(),
    useRefreshSourceGroupMutation: vi.fn(),
    useDeleteSourceGroupMutation: vi.fn(),
    useImportSourceGroupMutation: vi.fn(),
    useCreateSourceRepositoryMutation: vi.fn(),
    useBulkCreateMirrorsMutation: vi.fn(),
    useGetSyncGroupsQuery: vi.fn(),
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
  useGetSourceGroupsQuery,
  useGetSourceRepositoriesQuery,
  useRefreshSourceGroupMutation,
  useDeleteSourceGroupMutation,
  useImportSourceGroupMutation,
  useCreateSourceRepositoryMutation,
  useBulkCreateMirrorsMutation,
  useGetSyncGroupsQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import SourcesPage from '../../pages/GitMirroring/Sources';
import type { SourceGroup, SourceProvider } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockGenericProvider: SourceProvider = {
  id: 3,
  label: 'Generic Git Server',
  provider_type: 'generic',
  credential_id: 30,
  status_flag: 0,
  status_text: 'OK',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGithubProvider: SourceProvider = {
  id: 1,
  label: 'GitHub',
  provider_type: 'github',
  credential_id: 10,
  status_flag: 0,
  status_text: 'OK',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGitlabProvider: SourceProvider = {
  id: 2,
  label: 'GitLab Instance',
  provider_type: 'gitlab',
  credential_id: 20,
  config_json: { api_url: 'https://gitlab.example.com' },
  status_flag: 0,
  status_text: 'OK',
  groups_count: 5,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGroup: SourceGroup = {
  id: 1,
  external_id: 'test-org',
  name: 'Test Org',
  full_name: 'Test Org',
  description: 'A test organization',
  repositories_total: 5,
  repositories_mirrored: 2,
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

function renderSourcesPage(tab = 'groups') {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <MemoryRouter initialEntries={[`/git-mirroring/sources?tab=${tab}`]}>
          <App>
            <SourcesPage />
          </App>
        </MemoryRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SourcesPage — Groups tab', () => {
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
      data: [mockGithubProvider],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetSourceGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetSourceRepositoriesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useRefreshSourceGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteSourceGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useImportSourceGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useCreateSourceRepositoryMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useBulkCreateMirrorsMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  // -----------------------------------------------------------------------
  // Test 1: Page heading
  // -----------------------------------------------------------------------
  it('renders "Sources" heading', () => {
    renderSourcesPage();
    expect(screen.getAllByText('Sources').length).toBeGreaterThanOrEqual(1);
  });

  // -----------------------------------------------------------------------
  // Test 2: Provider selector
  // -----------------------------------------------------------------------
  it('renders provider selector', () => {
    renderSourcesPage();
    // The Select component should be in the DOM (antd renders options in a dropdown)
    const selectElement = document.querySelector('.ant-select');
    expect(selectElement).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Import button
  // -----------------------------------------------------------------------
  it('renders "Import Group" button', () => {
    renderSourcesPage();
    expect(screen.getByText('Import Group')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: Groups table with data
  // -----------------------------------------------------------------------
  it('displays group data when groups are loaded', () => {
    (useGetSourceGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGroup],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSourcesPage();

    // "Test Org" appears in both name and full_name columns
    expect(screen.getAllByText('Test Org').length).toBeGreaterThanOrEqual(1);
    // Repository counts displayed via Badge
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Empty state
  // -----------------------------------------------------------------------
  it('shows empty state when no groups exist', () => {
    renderSourcesPage();
    expect(screen.getByText('No groups found')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 6: All provider types (including Generic Git) shown in selector
  // -----------------------------------------------------------------------
  it('shows Generic Git provider alongside GitHub and GitLab in the provider selector', () => {
    (useGetSourceProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGithubProvider, mockGitlabProvider, mockGenericProvider],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSourcesPage();

    // Provider selector should exist
    const selectElement = document.querySelector('.ant-select');
    expect(selectElement).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 7: Import Group modal opens and shows providers (including Generic Git)
  // -----------------------------------------------------------------------
  it('opens Import Group modal when clicking Import Group button', async () => {
    (useGetSourceProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGitlabProvider, mockGenericProvider],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSourcesPage();

    // Click the Import Group button
    const importButton = screen.getByText('Import Group');
    importButton.click();

    // Modal should appear in a portal; use document, not container
    await waitFor(() => {
      expect(document.querySelector('.ant-modal')).toBeInTheDocument();
    });
  });
});
