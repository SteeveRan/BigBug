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
  source_provider: null,
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
    expect(screen.getByText('Info')).toBeInTheDocument();
    expect(screen.getByText('Releases')).toBeInTheDocument();
    expect(screen.getByText('README')).toBeInTheDocument();
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
  // Test 6: Activity block — last commit date (source_pushed_at)
  // -----------------------------------------------------------------------
  it('displays last commit date in Activity block', () => {
    renderDetailPage();
    // source_pushed_at is shown as both "Last Commit" and "Last Commit Date"
    expect(screen.getByText('Last Commit')).toBeInTheDocument();
    expect(screen.getByText('Last Commit Date')).toBeInTheDocument();
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
});
