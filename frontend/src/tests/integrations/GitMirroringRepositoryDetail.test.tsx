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
import type { SourceRepository, SourceRepositoryRelease, Mirror } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockRepo: SourceRepository = {
  id: 10,
  external_id: '12345',
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
  source_group_name: 'Test Org',
  license_spdx: 'MIT',
  license_name: 'MIT License',
  latest_release_tag: 'v1.0.0',
  latest_release_name: 'Release v1.0.0',
  latest_release_published_at: '2026-06-01T00:00:00Z',
  discovery_status: 0,
  discovery_status_text: 'OK',
  has_readme: true,
  is_mirrored: true,
  mirrors_count: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockRelease: SourceRepositoryRelease = {
  id: 1,
  release_tag: 'v1.0.0',
  release_name: 'Release v1.0.0',
  release_body: 'Initial release',
  is_prerelease: false,
  published_at: '2026-06-01T00:00:00Z',
  html_url: 'https://github.com/owner/test-repo/releases/tag/v1.0.0',
};

const mockMirror: Mirror = {
  id: 1,
  source_repository_id: 10,
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
  is_active: true,
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
  // Test 2: Tabs are rendered
  // -----------------------------------------------------------------------
  it('renders tabs: Info, Releases, README, Mirrors', () => {
    renderDetailPage();
    expect(screen.getByText('Info')).toBeInTheDocument();
    expect(screen.getByText('Releases')).toBeInTheDocument();
    expect(screen.getByText('README')).toBeInTheDocument();
    // Mirrors tab label is dynamic: "Mirrors (N)" where N is mirrors count (0 when empty)
    expect(screen.getByText('Mirrors (0)')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: License and stars display
  // -----------------------------------------------------------------------
  it('displays license, stars, and forks info', () => {
    renderDetailPage();
    // License renders license_spdx ("MIT") inside a Tag, not license_name ("MIT License")
    expect(screen.getByText('MIT')).toBeInTheDocument();
    // Stars is unique on the Info tab
    expect(screen.getByText('5')).toBeInTheDocument();
    // "2" appears twice (Forks AND Mirrors Count); use getAllByText
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1);
  });

  // -----------------------------------------------------------------------
  // Test 4: Latest release tag
  // -----------------------------------------------------------------------
  it('displays latest release tag', () => {
    renderDetailPage();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Loading spinner
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
