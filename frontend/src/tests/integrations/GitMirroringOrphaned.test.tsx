/**
 * @file GitMirroringOrphaned.test.tsx
 * @description Integration tests for the Git Mirroring Orphaned Mirrors page + RelinkModal
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../pages/GitMirroring/Orphaned/index.tsx, ../../pages/GitMirroring/Orphaned/RelinkModal.tsx, ../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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
    useGetOrphanedMirrorsQuery: vi.fn(),
    useReassignOrphanedMirrorMutation: vi.fn(),
    useMoveOrphanedTargetMutation: vi.fn(),
    useDeleteOrphanedMirrorMutation: vi.fn(),
    useCheckMirrorIntegrityMutation: vi.fn(),
    useGetProvidersQuery: vi.fn(),
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
  useGetOrphanedMirrorsQuery,
  useReassignOrphanedMirrorMutation,
  useMoveOrphanedTargetMutation,
  useDeleteOrphanedMirrorMutation,
  useCheckMirrorIntegrityMutation,
  useGetProvidersQuery,
  useGetSyncGroupsQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import OrphanedPage from '../../pages/GitMirroring/Orphaned';
import type { OrphanedMirror, SyncGroup, ResourceProvider } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockOrphaned1: OrphanedMirror = {
  mirror_id: 1,
  mirror_name: 'my-repo',
  source_url: 'https://github.com/org/my-repo.git',
  target_path: 'gitlab-group/my-repo',
  sync_group_name: 'Production Sync',
  gitlab_instance_url: 'https://gitlab.example.com',
  orphan_reason: 'credentials_invalid',
  orphan_reason_text: 'Credentials invalid or expired',
  detected_at: '2026-06-13T22:00:00Z',
};

const mockOrphaned2: OrphanedMirror = {
  mirror_id: 2,
  mirror_name: 'legacy-app',
  source_url: 'https://github.com/org/legacy-app.git',
  target_path: 'gitlab-group/archived/legacy-app',
  sync_group_name: null,
  gitlab_instance_url: 'https://gitlab.example.com',
  orphan_reason: 'provider_deleted',
  orphan_reason_text: 'Source provider was deleted',
  detected_at: '2026-06-12T15:30:00Z',
};

const mockOrphaned3: OrphanedMirror = {
  mirror_id: 3,
  mirror_name: 'missing-source',
  source_url: 'https://github.com/deleted/repo.git',
  target_path: 'gitlab-group/missing-source',
  sync_group_name: 'Default',
  gitlab_instance_url: 'https://gitlab2.example.com',
  orphan_reason: 'source_not_found',
  orphan_reason_text: 'Source repository not found',
  detected_at: '2026-06-11T08:00:00Z',
};

const mockOrphaned4: OrphanedMirror = {
  mirror_id: 4,
  mirror_name: 'manual-delete',
  source_url: 'https://github.com/org/manual-delete.git',
  target_path: 'gitlab-group/manual-delete',
  sync_group_name: 'Default',
  gitlab_instance_url: 'https://gitlab.example.com',
  orphan_reason: 'target_manual_delete',
  orphan_reason_text: 'Target was manually deleted in GitLab',
  detected_at: '2026-06-14T01:00:00Z',
};

const mockSyncGroupDefault: SyncGroup = {
  id: 1,
  name: 'Default',
  description: 'Default sync group',
  pipeline_id: null,
  pipeline: null,
  is_default: true,
  mirrors_count: 0,
  sync_cron: null,
  sync_enabled: false,
  sync_concurrency: 3,
  freshness_cron: null,
  freshness_enabled: false,
  freshness_concurrency: 3,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockSyncGroupProd: SyncGroup = {
  id: 2,
  name: 'Production',
  description: 'Production sync group',
  pipeline_id: 1,
  pipeline: null,
  is_default: false,
  mirrors_count: 5,
  sync_cron: '0 */6 * * *',
  sync_enabled: true,
  sync_concurrency: 3,
  freshness_cron: '0 0 * * *',
  freshness_enabled: true,
  freshness_concurrency: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGitlabInstance: ResourceProvider = {
  id: 1,
  domain: 'git',
  subtype: 'gitlab',
  category: 'system',
  direction: 'internal',
  name: 'gitlab-local',
  label: 'GitLab Local',
  description: null,
  base_url: 'https://gitlab.example.com',
  config: {},
  credential_id: null,
  owner_user_id: null,
  visibility: 'public',
  team_id: null,
  team_name: null,
  is_active: true,
  is_default: true,
  is_protected: false,
  verify_ssl: true,
  priority: 0,
  status_flag: 0,
  status_text: 'Connected',
  last_checked_at: '2026-06-13T12:00:00Z',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-13T12:00:00Z',
  has_credential: false,
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderOrphanedPage() {
  const store = createTestStore();
  const utils = render(
    <Provider store={store}>
      <BrowserRouter>
        <App>
          <OrphanedPage />
        </App>
      </BrowserRouter>
    </Provider>
  );
  return { store, ...utils };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('GitMirroring Orphaned Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetOrphanedMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [mockOrphaned1, mockOrphaned2, mockOrphaned3, mockOrphaned4], total: 4 },
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGitlabInstance],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockSyncGroupDefault, mockSyncGroupProd],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useReassignOrphanedMirrorMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({}),
      { isLoading: false },
    ]);

    (useMoveOrphanedTargetMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({}),
      { isLoading: false },
    ]);

    (useDeleteOrphanedMirrorMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({}),
      { isLoading: false },
    ]);

    (useCheckMirrorIntegrityMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  // ── Test 1 ──
  it('renders the page with mocked API', () => {
    renderOrphanedPage();

    const headings = screen.getAllByText('Orphaned Mirrors');
    expect(headings.length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText('Mirrors that have lost connection to their source or target')
    ).toBeInTheDocument();
  });

  // ── Test 2 ──
  it('shows table with orphaned mirrors', () => {
    renderOrphanedPage();

    expect(screen.getByText('my-repo')).toBeInTheDocument();
    expect(screen.getByText('legacy-app')).toBeInTheDocument();
    expect(screen.getByText('missing-source')).toBeInTheDocument();
    expect(screen.getByText('manual-delete')).toBeInTheDocument();
  });

  // ── Test 3 ──
  it('displays correct orphan reason color tags', () => {
    renderOrphanedPage();

    // Check for reason labels
    expect(screen.getByText('Credentials Invalid')).toBeInTheDocument();
    expect(screen.getByText('Provider Deleted')).toBeInTheDocument();
    expect(screen.getByText('Source Not Found')).toBeInTheDocument();
    expect(screen.getByText('Target Deleted')).toBeInTheDocument();
  });

  // ── Test 4 ──
  it('shows Empty when no orphaned mirrors', () => {
    (useGetOrphanedMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      error: null,
    });

    renderOrphanedPage();

    expect(
      screen.getByText('No orphaned mirrors found — all mirrors are properly connected')
    ).toBeInTheDocument();
  });

  // ── Test 5 ──
  it('opens RelinkModal on mirror name click', async () => {
    renderOrphanedPage();

    const mirrorNameLink = screen.getByText('my-repo');
    fireEvent.click(mirrorNameLink);

    await waitFor(() => {
      expect(screen.getByText('Re-link: my-repo')).toBeInTheDocument();
    });

    // Source URL appears in both table and modal — use getAllByText
    const sourceUrlElements = screen.getAllByText('https://github.com/org/my-repo.git');
    expect(sourceUrlElements.length).toBeGreaterThanOrEqual(1);

    // Orphan reason text appears in the modal mirror info
    expect(screen.getByText('Credentials invalid or expired')).toBeInTheDocument();
    // Target path appears in both table and modal — use getAllByText
    const targetPathElements = screen.getAllByText('gitlab-group/my-repo');
    expect(targetPathElements.length).toBeGreaterThanOrEqual(1);
  });

  // ── Test 6 ──
  it('reassign sends correct request', async () => {
    const reassignMock = vi.fn().mockResolvedValue({});
    (useReassignOrphanedMirrorMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      reassignMock,
      { isLoading: false },
    ]);

    renderOrphanedPage();

    // Open modal
    fireEvent.click(screen.getByText('my-repo'));

    await waitFor(() => {
      expect(screen.getByText('Re-link: my-repo')).toBeInTheDocument();
    });

    // Select a sync group
    const select = screen.getByText('Select Sync Group…');
    fireEvent.mouseDown(select.parentElement!);

    await waitFor(() => {
      expect(screen.getByText('Production')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Production'));

    // Click reassign button
    fireEvent.click(screen.getByText('Reassign to Sync Group'));

    await waitFor(() => {
      expect(reassignMock).toHaveBeenCalledWith({
        mirrorId: 1,
        syncGroupId: 2,
      });
    });
  });

  // ── Test 7 ──
  it('move target sends correct request', async () => {
    const moveMock = vi.fn().mockResolvedValue({});
    (useMoveOrphanedTargetMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      moveMock,
      { isLoading: false },
    ]);

    renderOrphanedPage();

    // Open modal
    fireEvent.click(screen.getByText('my-repo'));

    await waitFor(() => {
      expect(screen.getByText('Re-link: my-repo')).toBeInTheDocument();
    });

    // Switch to Move Target tab
    fireEvent.click(screen.getByText('Move Target'));

    await waitFor(() => {
      expect(
        screen.getByText('Change the GitLab target project path for this mirror.')
      ).toBeInTheDocument();
    });

    // Change target path
    const input = screen.getByPlaceholderText('New target path (e.g., org/group/project)');
    fireEvent.change(input, { target: { value: 'new-group/new-path' } });

    // Click update
    fireEvent.click(screen.getByText('Update Target Path'));

    await waitFor(() => {
      expect(moveMock).toHaveBeenCalledWith({
        mirrorId: 1,
        targetPath: 'new-group/new-path',
      });
    });
  });

  // ── Test 8 ──
  it('delete shows confirmation and sends request', async () => {
    const deleteMock = vi.fn().mockResolvedValue({});
    (useDeleteOrphanedMirrorMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      deleteMock,
      { isLoading: false },
    ]);

    const { container } = renderOrphanedPage();

    // Find the danger button in the actions column (type="text" + danger)
    const dangerButtons = container.querySelectorAll('.ant-btn-dangerous');
    expect(dangerButtons.length).toBeGreaterThan(0);
    fireEvent.click(dangerButtons[0] as HTMLElement);

    // Confirmation modal should appear
    await waitFor(() => {
      expect(
        screen.getByText('This will soft-delete the mirror. It can be restored within 30 days.')
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/Are you sure you want to delete mirror/)).toBeInTheDocument();

    // Click Delete confirmation button in the modal
    const modalDeleteBtn = screen.getByRole('button', { name: /Delete$/ });
    fireEvent.click(modalDeleteBtn);

    await waitFor(() => {
      expect(deleteMock).toHaveBeenCalledWith(1);
    });
  });

  // ── Test 9 ──
  it('search filter works', async () => {
    renderOrphanedPage();

    const searchInput = screen.getByPlaceholderText('Search by name or URL…');
    fireEvent.change(searchInput, { target: { value: 'legacy' } });

    await waitFor(() => {
      expect(useGetOrphanedMirrorsQuery).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'legacy' })
      );
    });
  });

  // ── Test 10 ──
  it('pagination works', async () => {
    (useGetOrphanedMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: {
        items: [mockOrphaned1, mockOrphaned2],
        total: 20,
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    const { container } = renderOrphanedPage();

    // Pagination should be present with first page active
    const paginationItems = container.querySelectorAll('.ant-pagination-item');
    expect(paginationItems.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('1')).toBeInTheDocument();

    // The Select component for page size should be in the pagination area
    const sizeChanger = container.querySelector('.ant-pagination-options-size-changer');
    expect(sizeChanger).toBeInTheDocument();
  });
});
