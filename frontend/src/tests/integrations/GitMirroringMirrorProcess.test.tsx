/**
 * @file GitMirroringMirrorProcess.test.tsx
 * @description Integration tests for the Mirror Process page (3 tabs)
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router, antd
 * @relatedFiles ../../pages/GitMirroring/Mirrors/Process.tsx, ../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { MemoryRouter, Route, Routes } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App } from 'antd';

// ---------------------------------------------------------------------------
// Mocks — must appear before any imports that use these modules
// ---------------------------------------------------------------------------

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...(actual as object),
    useNavigate: vi.fn(() => vi.fn()),
  };
});

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetMirrorDetailQuery: vi.fn(),
    useGetMirrorLogsV2Query: vi.fn(),
    useTriggerMirrorSyncMutation: vi.fn(),
    useTriggerFreshnessCheckMutation: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(() => ({
    hasPermission: vi.fn(() => true),
    hasAnyPermission: vi.fn(() => true),
    hasAllPermissions: vi.fn(() => true),
  })),
}));

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import authReducer from '../../store/authSlice';
import {
  useGetMirrorDetailQuery,
  useGetMirrorLogsV2Query,
  useTriggerMirrorSyncMutation,
  useTriggerFreshnessCheckMutation,
} from '../../store/api';
import MirrorProcessPage from '../../pages/GitMirroring/Mirrors/Process';
import type { MirrorDetail, MirrorLog } from '../../types';
import { STATUS_FLAG } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockSourceRepository = {
  id: 1,
  external_id: '123',
  name: 'test-repo',
  full_name: 'bigbug/test-repo',
  description: 'A test repository for mirroring',
  private: false,
  fork: false,
  archived: false,
  language: 'TypeScript',
  default_branch: 'main',
  html_url: 'https://github.com/bigbug/test-repo',
  clone_url: 'https://github.com/bigbug/test-repo.git',
  stars: 10,
  forks: 2,
  source_group_id: 1,
  source_group_name: 'BigBug Group',
  license_spdx: 'MIT',
  license_name: 'MIT License',
  latest_release_tag: 'v1.0.0',
  latest_release_name: 'Initial Release',
  latest_release_published_at: '2026-01-01T00:00:00Z',
  discovery_status: 0,
  discovery_status_text: 'OK',
  has_readme: true,
  is_mirrored: true,
  mirrors_count: 3,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

const mockSyncGroup = {
  id: 1,
  name: 'Default Sync Group',
  description: 'Default group for all mirrors',
  pipeline_id: 1,
  pipeline: {
    id: 1,
    name: 'Default Mirror Pipeline',
    description: 'Default pipeline for mirroring',
    gitlab_instance_id: 1,
    gitlab_instance: {
      id: 1,
      name: 'GitLab CE',
      url: 'https://gitlab.example.com',
      is_active: true,
      verify_ssl: true,
      is_default: true,
      default_group_id: 1,
      status_flag: 0,
      status_text: 'OK',
      last_checked_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    ref: 'main',
    default_variables: {},
    is_default: true,
    is_enabled: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    components: [],
  },
  is_default: true,
  mirrors_count: 5,
  sync_cron: '0 */6 * * *',
  sync_enabled: true,
  sync_concurrency: 3,
  freshness_cron: '0 0 * * *',
  freshness_enabled: true,
  freshness_concurrency: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockRecentLogs: MirrorLog[] = [
  {
    id: 1,
    mirror_id: 1,
    pipeline_run_id: 10,
    gitlab_pipeline_id: '456',
    gitlab_pipeline_url: 'https://gitlab.example.com/bigbug/test-project/-/pipelines/456',
    log_type: 'sync',
    status_flag: STATUS_FLAG.OK,
    status_text: 'Sync completed',
    message: 'All branches synced',
    source_commit_sha: 'abc1234def567890',
    source_commit_date: '2026-06-01T12:00:00Z',
    target_commit_sha: 'abc1234def567890',
    commits_behind: 0,
    duration_ms: 45000,
    triggered_by: 'admin',
    started_at: '2026-06-01T12:00:00Z',
    finished_at: '2026-06-01T12:00:45Z',
    created_at: '2026-06-01T12:00:45Z',
  },
  {
    id: 2,
    mirror_id: 1,
    pipeline_run_id: 11,
    log_type: 'freshness',
    status_flag: STATUS_FLAG.OK,
    status_text: 'Up to date',
    message: 'No divergence detected',
    source_commit_sha: 'xyz9876abc123ef',
    source_commit_date: '2026-06-02T08:00:00Z',
    target_commit_sha: 'abc1234def567890',
    commits_behind: 5,
    duration_ms: 5000,
    triggered_by: 'system',
    started_at: '2026-06-02T08:00:00Z',
    finished_at: '2026-06-02T08:00:05Z',
    created_at: '2026-06-02T08:00:05Z',
  },
];

const mockMirrorDetail: MirrorDetail = {
  id: 1,
  source_repository_id: 1,
  sync_group_id: 1,
  target_namespace: 'bigbug-mirrors',
  target_project_name: 'test-project',
  target_path: 'bigbug-mirrors/test-project',
  target_gitlab_name: 'GitLab CE',
  target_project_id: '42',
  target_web_url: 'https://gitlab.example.com/bigbug-mirrors/test-project',
  status_flag: STATUS_FLAG.OK,
  status_text: 'OK',
  discovery_status: 0,
  discovery_status_text: 'OK',
  last_sync_at: '2026-06-01T12:00:45Z',
  last_freshness_check_at: '2026-06-02T08:00:05Z',
  last_sync_status: 'OK',
  last_freshness_status: 'Up to date',
  last_known_commit_sha: 'abc1234def567890',
  last_known_commit_date: '2026-06-01T12:00:00Z',
  last_known_commit_author: 'admin',
  target_diverged_commits: 5,
  is_imported: true,
  is_active: true,
  source_repository: mockSourceRepository,
  sync_group: mockSyncGroup,
  mirror_logs: mockRecentLogs,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-01T12:00:45Z',
};

const mockPaginatedLogs: MirrorLog[] = [
  ...mockRecentLogs,
  {
    id: 3,
    mirror_id: 1,
    log_type: 'integrity',
    status_flag: STATUS_FLAG.OK,
    status_text: 'Integrity verified',
    message: 'All commits match',
    source_commit_sha: 'def5678abc901234',
    source_commit_date: '2026-06-03T10:00:00Z',
    commits_behind: 0,
    duration_ms: 120000,
    triggered_by: 'admin',
    started_at: '2026-06-03T10:00:00Z',
    finished_at: '2026-06-03T10:02:00Z',
    created_at: '2026-06-03T10:02:00Z',
    details: { checks: { hashes: 'valid', tags: 'synced' } },
  },
];

function createTestStore(): Store {
  return configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

const mockTriggerSyncFn = vi.fn();
const mockTriggerFreshnessFn = vi.fn();

describe('GitMirroringMirrorProcess', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    store = createTestStore();
    vi.clearAllMocks();
    mockTriggerSyncFn.mockReset();
    mockTriggerFreshnessFn.mockReset();

    (useGetMirrorDetailQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockMirrorDetail,
      isLoading: false,
      isError: false,
    });

    (useGetMirrorLogsV2Query as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockPaginatedLogs,
      isLoading: false,
      isError: false,
    });

    (useTriggerMirrorSyncMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockTriggerSyncFn,
      { isLoading: false },
    ]);

    (useTriggerFreshnessCheckMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockTriggerFreshnessFn,
      { isLoading: false },
    ]);
  });

  function renderPage(mirrorId = '1') {
    return render(
      <Provider store={store}>
        <MemoryRouter initialEntries={[`/git-mirroring/mirrors/${mirrorId}`]}>
          <Routes>
            <Route
              path="git-mirroring/mirrors/:id"
              element={
                <App>
                  <MirrorProcessPage />
                </App>
              }
            />
          </Routes>
        </MemoryRouter>
      </Provider>
    );
  }

  // ── Test 1: breadcrumbs and title ─────────────────────────────────────
  it('displays breadcrumbs and title with mirror name', () => {
    renderPage();

    // Breadcrumbs
    expect(screen.getByText('Git Mirroring')).toBeInTheDocument();
    expect(screen.getByText('Mirrors')).toBeInTheDocument();
    expect(screen.getByText('test-repo')).toBeInTheDocument();

    // Title
    expect(screen.getByText('Mirror Process — bigbug/test-repo')).toBeInTheDocument();
  });

  // ── Test 2: Process tab with source/target info ───────────────────────
  it('shows Process tab with source and target information', () => {
    renderPage();

    // Process tab is active by default
    expect(screen.getByText('Process')).toBeInTheDocument();

    // Source info (also appears in Configuration tab — use getAllByText)
    expect(screen.getAllByText('bigbug/test-repo').length).toBeGreaterThanOrEqual(1);

    // Target info
    expect(screen.getAllByText('GitLab CE').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('bigbug-mirrors/test-project').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Open in GitLab')).toBeInTheDocument();

    // Sync group (also appears in Configuration tab)
    expect(screen.getAllByText('Default Sync Group').length).toBeGreaterThanOrEqual(1);

    // Pipeline
    expect(screen.getByText('Default Mirror Pipeline (main)')).toBeInTheDocument();

    // Last sync (date format appears both in description and recent logs table)
    expect(screen.getAllByText(/6\/1\/2026/).length).toBeGreaterThanOrEqual(1);
  });

  // ── Test 3: Process tab shows recent logs table ───────────────────────
  it('shows recent logs table in Process tab', () => {
    renderPage();

    // Recent Logs card
    expect(screen.getByText('Recent Logs (2)')).toBeInTheDocument();

    // Table columns
    expect(screen.getByText('Log Type')).toBeInTheDocument();
    expect(screen.getByText('Started At')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();

    // Log type tags
    const syncTag = screen.getByText('sync');
    expect(syncTag).toBeInTheDocument();

    const freshnessTag = screen.getByText('freshness');
    expect(freshnessTag).toBeInTheDocument();

    // OK status tags
    const okTags = screen.getAllByText('OK');
    expect(okTags.length).toBeGreaterThanOrEqual(1);
  });

  // ── Test 4: Configuration tab with readonly fields ────────────────────
  it('shows Configuration tab with readonly fields', async () => {
    const user = userEvent.setup();
    renderPage();

    // Click Configuration tab
    const configTab = screen.getByText('Configuration');
    await user.click(configTab);

    // Source Repository card (title is unique to this tab)
    expect(screen.getByText('Source Repository')).toBeInTheDocument();
    expect(screen.getAllByText('bigbug/test-repo').length).toBeGreaterThanOrEqual(1);

    // Archived status
    expect(screen.getByText('No')).toBeInTheDocument(); // archived=No

    // License
    expect(screen.getByText('MIT')).toBeInTheDocument();

    // Default branch (also appears as Pipeline ref in Configuration tab — can match 2+ times)
    expect(screen.getAllByText('main').length).toBeGreaterThanOrEqual(1);

    // Target card (title also appears as Process tab Descriptions label)
    expect(screen.getAllByText('Target').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('bigbug-mirrors')).toBeInTheDocument();

    // Sync Group card (title also appears as Process tab Descriptions label)
    expect(screen.getAllByText('Sync Group').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('0 */6 * * *')).toBeInTheDocument();
    expect(screen.getByText('0 0 * * *')).toBeInTheDocument();

    // Pipeline card (title also appears as Process tab Descriptions label)
    expect(screen.getAllByText('Pipeline').length).toBeGreaterThanOrEqual(1);

    // Import status
    expect(screen.getByText('Import Status:')).toBeInTheDocument();
    expect(screen.getByText('Imported')).toBeInTheDocument();

    // Edit Config button (disabled)
    expect(screen.getByText('Edit Config')).toBeInTheDocument();
  });

  // ── Test 5: Logs tab with filters ─────────────────────────────────────
  it('shows Logs tab with filter selects', async () => {
    const user = userEvent.setup();
    renderPage();

    // Click Logs tab
    const logsTab = screen.getByText('Logs');
    await user.click(logsTab);

    // Filters should be present
    // Select for log_type
    const selectElements = screen.getAllByRole('combobox');
    expect(selectElements.length).toBeGreaterThanOrEqual(2);

    // Logs table column headers (also appear in Process tab's recent logs table)
    expect(screen.getAllByText('Log Type').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Started At').length).toBeGreaterThanOrEqual(1);

    // Log type tags visible in table — 'integrity' only in paginated logs (Logs tab)
    expect(screen.getByText('integrity')).toBeInTheDocument();
  });

  // ── Test 6: Loading state ─────────────────────────────────────────────
  it('shows loading spinner when data is loading', () => {
    (useGetMirrorDetailQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    renderPage();

    // Antd Spin renders as role="img" with aria-label="loading"
    const spinner = document.querySelector('.ant-spin');
    expect(spinner).toBeInTheDocument();
  });

  // ── Test 7: Error state ───────────────────────────────────────────────
  it('shows error alert when mirror fails to load', () => {
    (useGetMirrorDetailQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    renderPage();

    expect(screen.getByText('Failed to load mirror')).toBeInTheDocument();
  });
});
