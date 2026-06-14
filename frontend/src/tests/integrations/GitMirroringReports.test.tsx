/**
 * @file GitMirroringReports.test.tsx
 * @description Integration tests for the Git Mirroring Reports page (5 sub-tabs)
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../pages/GitMirroring/Reports/index.tsx, ../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App } from 'antd';
import userEvent from '@testing-library/user-event';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetDuplicatesReportQuery: vi.fn(),
    useGetStorageReportQuery: vi.fn(),
    useRefreshStorageReportMutation: vi.fn(),
    useGetStatusReportQuery: vi.fn(),
    useGetSyncsReportQuery: vi.fn(),
    useBulkReassignSyncGroupMutation: vi.fn(),
    useBulkChangeTargetGitlabMutation: vi.fn(),
    useBulkApplyPipelineMutation: vi.fn(),
    useGetMirrorsQuery: vi.fn(),
    useGetSyncGroupsQuery: vi.fn(),
    useGetPipelineConfigsQuery: vi.fn(),
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
  useGetDuplicatesReportQuery,
  useGetStorageReportQuery,
  useRefreshStorageReportMutation,
  useGetStatusReportQuery,
  useGetSyncsReportQuery,
  useBulkReassignSyncGroupMutation,
  useBulkChangeTargetGitlabMutation,
  useBulkApplyPipelineMutation,
  useGetMirrorsQuery,
  useGetSyncGroupsQuery,
  useGetPipelineConfigsQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import ReportsPage from '../../pages/GitMirroring/Reports';
import type {
  DuplicatesReport,
  DuplicateGroup,
  DuplicateMirrorItem,
  StorageReport,
  StorageSummary,
  MirrorStorageItem,
  StatusReport,
  StatusCountItem,
  MirrorStatusItem,
  SyncsReport,
  DailySyncsItem,
  SyncGroupSyncsItem,
  TopSyncMirrorItem,
  Mirror,
  SyncGroup,
  PipelineListItem,
} from '../../types';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockDuplicateMirrorItem: DuplicateMirrorItem = {
  mirror_id: 1,
  source_url: 'https://github.com/owner/repo.git',
  target_gitlab_instance_name: 'gitlab-local',
  target_path: 'gitlab-ns/repo',
  status_flag: 0,
  status_text: 'OK',
  created_at: '2026-01-15T10:30:00Z',
  sync_group_name: 'default',
};

const mockDuplicateGroup: DuplicateGroup = {
  source_url: 'https://github.com/owner/repo.git',
  mirror_count: 2,
  mirrors: [
    mockDuplicateMirrorItem,
    {
      ...mockDuplicateMirrorItem,
      mirror_id: 2,
      target_path: 'gitlab-ns/repo-copy',
      sync_group_name: 'backup',
    },
  ],
};

const mockDuplicatesReport: DuplicatesReport = {
  warning: 'Found 1 duplicate group(s) with 2 mirrors total',
  total_groups: 1,
  total_mirrors: 2,
  groups: [mockDuplicateGroup],
};

const mockEmptyDuplicatesReport: DuplicatesReport = {
  warning: '',
  total_groups: 0,
  total_mirrors: 0,
  groups: [],
};

const mockMirrorStorageItem: MirrorStorageItem = {
  mirror_id: 1,
  source_url: 'https://github.com/owner/repo.git',
  target_gitlab_instance_name: 'gitlab-local',
  target_path: 'gitlab-ns/repo',
  sync_group_name: 'default',
  repo_size_bytes: 52428800,
  history_size_bytes: 10485760,
  total_size_bytes: 62914560,
  error: null,
  accessible: true,
};

const mockStorageSummary: StorageSummary = {
  key: 'gitlab-local',
  repo_size_bytes: 52428800,
  history_size_bytes: 10485760,
  total_size_bytes: 62914560,
};

const mockGrandTotalSummary: StorageSummary = {
  key: 'grand_total',
  repo_size_bytes: 52428800,
  history_size_bytes: 10485760,
  total_size_bytes: 62914560,
};

const mockStorageReport: StorageReport = {
  items: [mockMirrorStorageItem],
  by_gitlab_instance: [mockStorageSummary],
  by_sync_group: [{ ...mockStorageSummary, key: 'default' }],
  grand_total: mockGrandTotalSummary,
  collected_at: '2026-06-13T10:00:00Z',
  is_stale: false,
  collection_status: 'complete',
};

const mockStatusCountItem: StatusCountItem = {
  status_flag: 0,
  status_text: 'OK',
  count: 5,
  label: 'OK',
};

const mockMirrorStatusItem: MirrorStatusItem = {
  mirror_id: 1,
  source_url: 'https://github.com/owner/repo.git',
  status_flag: 0,
  status_text: 'OK',
  target_path: 'gitlab-ns/repo',
  sync_group_name: 'default',
};

const mockStatusReport: StatusReport = {
  status_counts: [mockStatusCountItem],
  total_mirrors: 5,
  ok_mirrors: [mockMirrorStatusItem],
  failed_mirrors: [],
  warning_mirrors: [],
  in_progress_mirrors: [],
  pending_mirrors: [],
};

const mockDailySyncsItem: DailySyncsItem = {
  date: '2026-06-12',
  total: 10,
  successful: 8,
  failed: 2,
  stale: 0,
};

const mockSyncGroupSyncsItem: SyncGroupSyncsItem = {
  sync_group_name: 'default',
  total: 10,
  successful: 8,
  failed: 2,
  stale: 0,
};

const mockTopSyncMirrorItem: TopSyncMirrorItem = {
  mirror_id: 1,
  source_url: 'https://github.com/owner/repo.git',
  taget_path: 'gitlab-ns/repo',
  count: 20,
};

const mockSyncsReport: SyncsReport = {
  period_start: '2026-06-01',
  period_end: '2026-06-13',
  daily: [mockDailySyncsItem],
  by_sync_group: [mockSyncGroupSyncsItem],
  top_by_syncs: [mockTopSyncMirrorItem],
  top_by_errors: [],
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
    external_id: 'ext-10',
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

const mockPipeline: PipelineListItem = {
  id: 1,
  name: 'ci-mirror-pipeline',
  is_default: true,
  mirrors_count: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderReportsPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <ReportsPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    // Default mocks for all hooks used by any tab
    (useGetDuplicatesReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });
    (useGetStorageReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });
    (useRefreshStorageReportMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useGetStatusReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });
    (useGetSyncsReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });
    (useBulkReassignSyncGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useBulkChangeTargetGitlabMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useBulkApplyPipelineMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useGetMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  // -----------------------------------------------------------------------
  // Test 1: Page heading
  // -----------------------------------------------------------------------
  it('renders "Git Mirroring Reports" heading', () => {
    renderReportsPage();
    expect(screen.getByText('Git Mirroring Reports')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Renders all 5 tabs
  // -----------------------------------------------------------------------
  it('renders all five report tabs', () => {
    renderReportsPage();

    expect(screen.getByText('Duplicates')).toBeInTheDocument();
    expect(screen.getByText('Storage')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Syncs')).toBeInTheDocument();
    expect(screen.getByText('Bulk Operations')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Duplicates tab — shows success alert when no duplicates
  // -----------------------------------------------------------------------
  it('shows success alert in Duplicates tab when no duplicates detected', async () => {
    (useGetDuplicatesReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockEmptyDuplicatesReport,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderReportsPage();

    await waitFor(() => {
      expect(screen.getByText('Дубликаты не обнаружены')).toBeInTheDocument();
      expect(screen.getByText(/Все зеркала уникальны/)).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test 4: Duplicates tab — shows warning alert and table when duplicates exist
  // -----------------------------------------------------------------------
  it('shows warning alert and expandable table in Duplicates tab when duplicates exist', async () => {
    (useGetDuplicatesReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockDuplicatesReport,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderReportsPage();

    await waitFor(() => {
      expect(screen.getByText(mockDuplicatesReport.warning)).toBeInTheDocument();
      expect(screen.getByText('https://github.com/owner/repo.git')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument(); // mirror_count
    });
  });

  // -----------------------------------------------------------------------
  // Test 5: Storage tab — shows storage data and summary
  // -----------------------------------------------------------------------
  it('shows storage data and summary cards in Storage tab', async () => {
    (useGetStorageReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockStorageReport,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderReportsPage();

    // Click the Storage tab
    const storageTab = screen.getByText('Storage');
    await userEvent.click(storageTab);

    await waitFor(() => {
      expect(screen.getByText('Общий итог')).toBeInTheDocument();
      expect(screen.getByText('По GitLab Instance')).toBeInTheDocument();
      expect(screen.getByText('По Sync Group')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test 6: Status tab — shows donut chart and status table
  // -----------------------------------------------------------------------
  it('shows donut chart and status table in Status tab', async () => {
    (useGetStatusReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockStatusReport,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderReportsPage();

    const statusTab = screen.getByText('Status');
    await userEvent.click(statusTab);

    await waitFor(() => {
      // Donut chart should render SVG
      expect(document.querySelector('svg')).toBeInTheDocument();
      expect(screen.getByText('OK')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test 7: Syncs tab — shows date picker and daily table
  // -----------------------------------------------------------------------
  it('shows date range picker and syncs tables in Syncs tab', async () => {
    (useGetSyncsReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockSyncsReport,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderReportsPage();

    const syncsTab = screen.getByText('Syncs');
    await userEvent.click(syncsTab);

    await waitFor(() => {
      expect(screen.getByText('По дням')).toBeInTheDocument();
      expect(screen.getByText('По Sync Group')).toBeInTheDocument();
      expect(screen.getByText('Топ-10 по синхронизациям')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test 8: Bulk Operations tab — shows mirror selector and operation type
  // -----------------------------------------------------------------------
  it('shows mirror selector and operation controls in Bulk Operations tab', async () => {
    (useGetMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockMirror],
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
    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockPipeline],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderReportsPage();

    const bulkTab = screen.getByText('Bulk Operations');
    await userEvent.click(bulkTab);

    await waitFor(() => {
      expect(screen.getByText('Select Mirrors:')).toBeInTheDocument();
      expect(screen.getByText('Operation:')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test 9: Smoke test — renders without crashing
  // -----------------------------------------------------------------------
  it('renders without crashing (smoke test)', () => {
    const { container } = renderReportsPage();
    expect(container).toBeTruthy();
  });
});
