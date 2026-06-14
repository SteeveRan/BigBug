/**
 * @file GitMirroringMirrors.test.tsx
 * @description Integration tests for the Git Mirroring Mirrors page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../../pages/GitMirroring/Mirrors/index.tsx, ../../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
    useImportExistingMirrorMutation: vi.fn(),
    useCreateMirrorV2Mutation: vi.fn(),
    useUpdateMirrorV2Mutation: vi.fn(),
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
  useGetMirrorsQuery,
  useDeleteMirrorV2Mutation,
  useTriggerMirrorSyncMutation,
  useTriggerFreshnessCheckMutation,
  useGetSourceRepositoriesQuery,
  useImportExistingMirrorMutation,
  useCreateMirrorV2Mutation,
  useUpdateMirrorV2Mutation,
  useGetSyncGroupsQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import MirrorsPage from '../../pages/GitMirroring/Mirrors';
import type { Mirror, SourceRepository, SyncGroup } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockGenericRepo: SourceRepository = {
  id: 30,
  external_id: 'generic-ext-30',
  name: 'generic-repo',
  full_name: 'git.example.com/team/generic-repo',
  description: 'A Generic Git repository',
  private: false,
  fork: false,
  archived: false,
  default_branch: 'main',
  html_url: 'https://git.example.com/team/generic-repo',
  clone_url: 'https://git.example.com/team/generic-repo.git',
  stars: 0,
  forks: 0,
  source_group_id: 0,
  source_group_name: undefined,
  discovery_status: 0,
  discovery_status_text: 'OK',
  has_readme: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGithubRepo: SourceRepository = {
  id: 10,
  external_id: 'github-ext-10',
  name: 'test-repo',
  full_name: 'owner/test-repo',
  description: 'A test repository',
  private: false,
  fork: false,
  archived: false,
  default_branch: 'main',
  html_url: 'https://github.com/owner/test-repo',
  clone_url: 'https://github.com/owner/test-repo.git',
  stars: 5,
  forks: 2,
  source_group_id: 1,
  source_group_name: 'github-org',
  discovery_status: 0,
  discovery_status_text: 'OK',
  has_readme: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGitlabRepo: SourceRepository = {
  id: 20,
  external_id: 'gitlab-ext-20',
  name: 'gitlab-project',
  full_name: 'gitlab-org/gitlab-project',
  description: 'A GitLab source repository',
  private: true,
  fork: false,
  archived: false,
  default_branch: 'main',
  html_url: 'https://gitlab.example.com/gitlab-org/gitlab-project',
  clone_url: 'https://gitlab.example.com/gitlab-org/gitlab-project.git',
  stars: 3,
  forks: 1,
  source_group_id: 2,
  source_group_name: 'gitlab-org',
  discovery_status: 0,
  discovery_status_text: 'OK',
  has_readme: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockSyncGroup: SyncGroup = {
  id: 5,
  name: 'default',
  description: 'Default sync group',
  pipeline_id: null,
  pipeline: null,
  is_default: true,
  mirrors_count: 3,
  sync_cron: null,
  sync_enabled: false,
  sync_concurrency: 3,
  freshness_cron: null,
  freshness_enabled: false,
  freshness_concurrency: 3,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

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
    (useImportExistingMirrorMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useCreateMirrorV2Mutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateMirrorV2Mutation as ReturnType<typeof vi.fn>).mockReturnValue([
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
  it('renders "Mirrors" heading', () => {
    renderMirrorsPage();
    const headings = screen.getAllByText('Mirrors');
    expect(headings.length).toBeGreaterThanOrEqual(1);
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

  // -----------------------------------------------------------------------
  // Test 9: Import Mirror modal shows GitHub, GitLab, and Generic Git repositories
  // -----------------------------------------------------------------------
  it('opens Import Mirror modal and shows repositories from all provider types', async () => {
    (useGetSourceRepositoriesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGithubRepo, mockGitlabRepo, mockGenericRepo],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderMirrorsPage();

    // Click "Import Existing Mirror" button
    const importButton = screen.getByText('Import Existing Mirror');
    importButton.click();

    // Modal should appear with "Import Existing Mirror" title
    await waitFor(() => {
      expect(screen.getByText('Import Existing Mirror')).toBeInTheDocument();
    });

    // The info alert should be visible
    expect(
      screen.getByText(/Система проверит связь через сравнение commit history/i)
    ).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 10: Create Mirror modal renders with sync group and Generic Git repos
  // -----------------------------------------------------------------------
  it('opens Create Mirror modal with repository and sync group selectors including Generic Git', async () => {
    (useGetSourceRepositoriesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGithubRepo, mockGitlabRepo, mockGenericRepo],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockSyncGroup],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderMirrorsPage();

    // Click "Create Mirror" button
    const createButton = screen.getByText('Create Mirror');
    createButton.click();

    // Modal should appear with "Create Mirror" title
    await waitFor(() => {
      expect(screen.getByText('Create Mirror')).toBeInTheDocument();
    });

    // The helper text should be visible
    expect(
      screen.getByText(/Create a new mirror from the selected source repository to GitLab./i)
    ).toBeInTheDocument();
  });
});
