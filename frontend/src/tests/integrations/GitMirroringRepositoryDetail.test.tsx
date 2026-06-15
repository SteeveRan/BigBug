/**
 * @file GitMirroringRepositoryDetail.test.tsx
 * @description Integration tests for the Git Mirroring Repository Detail page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../../pages/GitMirroring/Repositories/Detail.tsx, ../../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter, Routes, Route } from 'react-router';
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
    useGetSourceRepositoryQuery: vi.fn(),
    useGetRepositoryReleasesQuery: vi.fn(),
    useGetRepositoryReadmeQuery: vi.fn(),
    useGetMirrorsQuery: vi.fn(),
    useRefreshSourceRepositoryMutation: vi.fn(),
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
  useGetSourceRepositoryQuery,
  useGetRepositoryReleasesQuery,
  useGetRepositoryReadmeQuery,
  useGetMirrorsQuery,
  useRefreshSourceRepositoryMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import RepositoryDetailPage from '../../pages/GitMirroring/Repositories/Detail';
import type { SourceRepository } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockRepo: SourceRepository = {
  id: 10,
  source_provider_id: 1,
  source_group_id: 1,
  name: 'test-repo',
  full_name: 'owner/test-repo',
  web_url: 'https://github.com/owner/test-repo',
  clone_url_https: 'https://github.com/owner/test-repo.git',
  clone_url_ssh: 'git@github.com:owner/test-repo.git',
  description: 'A test repository',
  language: 'TypeScript',
  stars_count: 5,
  forks_count: 2,
  is_private: false,
  default_branch: 'main',
  license_spdx: 'MIT',
  license_name: 'MIT License',
  readme_html: '<h1>README</h1>',
  readme_fetched_at: '2026-01-01T00:00:00Z',
  latest_release_tag: 'v1.0.0',
  latest_release_name: 'Release v1.0.0',
  latest_release_date: '2026-06-01T00:00:00Z',
  latest_release_url: 'https://github.com/owner/test-repo/releases/tag/v1.0.0',
  latest_prerelease_tag: 'v2.0.0-beta.1',
  latest_prerelease_name: 'Beta 1',
  latest_prerelease_date: '2026-06-10T00:00:00Z',
  latest_prerelease_url: 'https://github.com/owner/test-repo/releases/tag/v2.0.0-beta.1',
  is_archived: false,
  is_fork: false,
  is_disabled: false,
  discovery_status: 'existing',
  discovered_at: '2026-01-01T00:00:00Z',
  last_seen_at: '2026-06-01T00:00:00Z',
  source_created_at: '2025-01-01T00:00:00Z',
  source_updated_at: '2026-06-01T00:00:00Z',
  source_pushed_at: '2026-06-01T12:00:00Z',
  is_deleted: false,
  deleted_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  // ---- Metadata fetch status ----
  status_flag: 0,
  status_text: null,
  // ---- Last commit metadata ----
  last_commit_sha: 'abc1234def5678abcdef1234567890abcdef12',
  last_commit_date: '2026-06-15T00:00:00Z',
  last_commit_author: 'Test Author',
  last_commit_message: 'Test commit message',
  // ---- Provider type ----
  provider_type: 'github',
  source_provider: {
    id: 1,
    label: 'GitHub',
    provider_type: 'github',
    credential_id: null,
    credential: undefined,
    is_anon: false,
    is_builtin: false,
    status_flag: 0,
    status_text: 'OK',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  source_group: null,
  mirrors: [],
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderDetailPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/git-mirroring/repositories/10']}>
          <App>
            <Routes>
              <Route path="/git-mirroring/repositories/:id" element={<RepositoryDetailPage />} />
            </Routes>
          </App>
        </MemoryRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RepositoryDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetSourceRepositoryQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockRepo,
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetRepositoryReleasesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetRepositoryReadmeQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useRefreshSourceRepositoryMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  // -----------------------------------------------------------------------
  // Test 1: Repository info is displayed
  // -----------------------------------------------------------------------
  it('renders repository name and description', () => {
    renderDetailPage();
    // "owner/test-repo" appears in both breadcrumb and Descriptions — use getAllByText
    expect(screen.getAllByText('owner/test-repo').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('A test repository')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Tabs are rendered (3 tabs: Info, Releases, README)
  // -----------------------------------------------------------------------
  it('renders tabs: Info, Releases, README (no separate Mirrors tab)', () => {
    renderDetailPage();
    // Tab labels — use getAllByText because "README" may also appear as a Card title in the Info tab
    expect(screen.getByText('Info')).toBeInTheDocument();
    expect(screen.getByText('Releases')).toBeInTheDocument();
    expect(screen.getAllByText('README').length).toBeGreaterThanOrEqual(1);
  });

  // -----------------------------------------------------------------------
  // Test 3: Two-column info blocks
  // -----------------------------------------------------------------------
  it('displays Full Name, Description, Web URL in first column', () => {
    renderDetailPage();
    // Web URL link
    expect(screen.getByText('https://github.com/owner/test-repo')).toBeInTheDocument();
    // Description
    expect(screen.getByText('A test repository')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: License, stars, language, archived, fork in second column
  // -----------------------------------------------------------------------
  it('displays license, stars, language, archived and fork info', () => {
    renderDetailPage();
    expect(screen.getByText('MIT')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
    // Stars count
    expect(screen.getByText('5')).toBeInTheDocument();
    // Archived/Fork render as "No"
    const noElements = screen.getAllByText('No');
    expect(noElements.length).toBeGreaterThanOrEqual(2);
  });

  // -----------------------------------------------------------------------
  // Test 5: Activity block — latest release tag
  // -----------------------------------------------------------------------
  it('displays latest release tag in Activity block', () => {
    renderDetailPage();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 6: Activity block — last commit details
  // -----------------------------------------------------------------------
  it('displays last commit details in Activity block', () => {
    renderDetailPage();
    // "Last Commit" column header
    expect(screen.getByText('Last Commit')).toBeInTheDocument();
    // The commit date formatted as UTC
    expect(screen.getByText('2026-06-15T00:00:00.000Z')).toBeInTheDocument();
    // The commit message
    expect(screen.getByText('Test commit message')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 7: Mirrors table inside Info tab ("Mirrors (N)")
  // -----------------------------------------------------------------------
  it('displays mirrors section inside Info tab', () => {
    renderDetailPage();
    expect(screen.getByText('Mirrors (0)')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Loading spinner
  // -----------------------------------------------------------------------
  it('shows loading spinner when repository data is loading', () => {
    (useGetSourceRepositoryQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    const { container } = renderDetailPage();
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // WP10b.1: Shows banner + skeleton when status_flag is 3
  // -----------------------------------------------------------------------
  it('shows banner and skeleton when status_flag is 3', () => {
    const fetchingRepo = { ...mockRepo, status_flag: 3 };
    (useGetSourceRepositoryQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: fetchingRepo,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderDetailPage();

    // Info banner
    expect(
      screen.getByText('Metadata is being fetched in background...')
    ).toBeInTheDocument();

    // Skeleton indicators — antd adds 'ant-skeleton' class
    const skeletons = document.querySelectorAll('.ant-skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // -----------------------------------------------------------------------
  // WP10b.2: Refresh button is disabled when status_flag is 3
  // -----------------------------------------------------------------------
  it('blocks refresh button when status_flag is 3', () => {
    const fetchingRepo = { ...mockRepo, status_flag: 3 };
    (useGetSourceRepositoryQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: fetchingRepo,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderDetailPage();

    const refreshBtn = screen.getByText('Refresh Metadata').closest('button');
    expect(refreshBtn).toBeDisabled();
  });

  // -----------------------------------------------------------------------
  // WP10b.3: Shows provider_type in Repository Info
  // -----------------------------------------------------------------------
  it('shows provider_type in Repository Info', () => {
    renderDetailPage();

    // The provider_type appears inside a <Tag> in the Repository Info card
    expect(screen.getByText('Provider Type')).toBeInTheDocument();
    expect(screen.getByText('github')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // WP10b.4: Activity section renders in 3 columns
  // -----------------------------------------------------------------------
  it('renders Activity section in 3 columns', () => {
    renderDetailPage();

    // Three column headers
    expect(screen.getByText('Last Commit')).toBeInTheDocument();
    expect(screen.getByText('Latest Release')).toBeInTheDocument();
    expect(screen.getByText('Latest Pre-release')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // WP10b.5: Shows commit SHA truncated to 7 chars
  // -----------------------------------------------------------------------
  it('shows commit sha truncated to 7 chars', () => {
    renderDetailPage();

    // The sha 'abc1234def5678abcdef1234567890abcdef12' truncated to 'abc1234'
    expect(screen.getByText('abc1234')).toBeInTheDocument();
    // The full 40-char SHA should NOT be present
    expect(
      screen.queryByText('abc1234def5678abcdef1234567890abcdef12')
    ).not.toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // WP10b.6: Shows "No data" for empty Activity fields
  // -----------------------------------------------------------------------
  it('shows no data for empty Activity fields', () => {
    const emptyActivityRepo: SourceRepository = {
      ...mockRepo,
      last_commit_sha: null,
      last_commit_date: null,
      last_commit_author: null,
      last_commit_message: null,
      latest_release_tag: null,
      latest_release_name: null,
      latest_release_date: null,
      latest_release_url: null,
      latest_prerelease_tag: null,
      latest_prerelease_name: null,
      latest_prerelease_date: null,
      latest_prerelease_url: null,
    };
    (useGetSourceRepositoryQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: emptyActivityRepo,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderDetailPage();

    // All three Activity columns should show "No data"
    const noDataElements = screen.getAllByText('No data');
    // The Activity card has exactly 3 columns each showing "No data".
    // Other cards may also render "No data" (e.g. Empty descriptions),
    // so we check for at least 3 rather than exactly 3.
    expect(noDataElements.length).toBeGreaterThanOrEqual(3);
  });
});
