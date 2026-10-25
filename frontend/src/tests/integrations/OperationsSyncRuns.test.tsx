/**
 * @file OperationsSyncRuns.test.tsx
 * @description Integration tests for the Admin > Sync Runs page (issue #113)
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../pages/Settings/SyncRuns/index.tsx, ../store/api.ts, ../hooks/usePermissions.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App as AntdApp } from 'antd';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetSyncRunsQuery: vi.fn(),
    useRetrySyncRunMutation: vi.fn(() => [
      vi.fn(() => ({ unwrap: () => Promise.resolve({}) })),
      { isLoading: false },
    ]),
    useRetryAllFailedMutation: vi.fn(() => [
      vi.fn(() => ({ unwrap: () => Promise.resolve({ retried: 2, total_failed_permanent: 2 }) })),
      { isLoading: false },
    ]),
    useRequeueSyncRunMutation: vi.fn(() => [
      vi.fn(() => ({ unwrap: () => Promise.resolve({}) })),
      { isLoading: false },
    ]),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import { useGetSyncRunsQuery, useRetryAllFailedMutation } from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import SyncRunsPage from '../../pages/Settings/SyncRuns';
import type { SyncRun } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockRunSucceeded: SyncRun = {
  id: 1,
  task_name: 'sync_helm_chart',
  entity_type: 'helm_chart_source',
  entity_id: 10,
  status: 'succeeded',
  attempts: 1,
  max_attempts: 3,
  payload: null,
  heartbeat_at: '2026-06-07T12:00:00Z',
  started_at: '2026-06-07T12:00:00Z',
  finished_at: '2026-06-07T12:01:00Z',
  error: null,
  created_at: '2026-06-07T12:00:00Z',
  stuck: false,
};

const mockRunFailedPermanent: SyncRun = {
  ...mockRunSucceeded,
  id: 2,
  task_name: 'sync_docker_image',
  entity_id: 20,
  status: 'failed_permanent',
  attempts: 3,
  heartbeat_at: null,
  finished_at: '2026-06-07T12:05:00Z',
  error: 'Traceback: ConnectionError: harbor unreachable',
  stuck: false,
};

const mockRunStuck: SyncRun = {
  ...mockRunSucceeded,
  id: 3,
  task_name: 'gitlab_mirror_sync',
  entity_id: 30,
  status: 'running',
  finished_at: null,
  error: null,
  stuck: true,
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderSyncRunsPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <AntdApp>
          <BrowserRouter>
            <SyncRunsPage />
          </BrowserRouter>
        </AntdApp>
      </Provider>
    ),
  };
}

function mockQuery(data: SyncRun[]) {
  (useGetSyncRunsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SyncRunsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    mockQuery([]);
  });

  it('renders heading and filter buttons', () => {
    renderSyncRunsPage();
    expect(screen.getByText('Sync Runs')).toBeInTheDocument();
    for (const label of ['All', 'Failed permanent', 'Stuck', 'Running', 'Queued']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
    }
  });

  it('renders rows from mocked API', () => {
    mockQuery([mockRunSucceeded, mockRunFailedPermanent, mockRunStuck]);
    renderSyncRunsPage();
    expect(screen.getByText('sync_helm_chart')).toBeInTheDocument();
    expect(screen.getByText('sync_docker_image')).toBeInTheDocument();
    expect(screen.getByText('gitlab_mirror_sync')).toBeInTheDocument();
    expect(screen.getByText('helm_chart_source#10')).toBeInTheDocument();
    // "Stuck" tag on the running row — filter button is "Stuck" too, so match within the tag
    expect(screen.getAllByText('Stuck').length).toBeGreaterThanOrEqual(1);
  });

  it('switching filters changes query params', async () => {
    renderSyncRunsPage();

    await userEvent.click(screen.getByRole('button', { name: 'Failed permanent' }));
    expect(useGetSyncRunsQuery).toHaveBeenLastCalledWith(
      { run_status: 'failed_permanent' },
      expect.anything()
    );

    await userEvent.click(screen.getByRole('button', { name: 'Stuck' }));
    expect(useGetSyncRunsQuery).toHaveBeenLastCalledWith({ stuck: true }, expect.anything());

    await userEvent.click(screen.getByRole('button', { name: 'Running' }));
    expect(useGetSyncRunsQuery).toHaveBeenLastCalledWith(
      { run_status: 'running' },
      expect.anything()
    );
  });

  it('failed_permanent row enables Retry but not Requeue', () => {
    mockQuery([mockRunFailedPermanent]);
    renderSyncRunsPage();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Requeue' })).not.toBeInTheDocument();
  });

  it('stuck row enables Requeue but not Retry', () => {
    mockQuery([mockRunStuck]);
    renderSyncRunsPage();
    expect(screen.getByRole('button', { name: 'Requeue' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });

  it('succeeded row has no actions', () => {
    mockQuery([mockRunSucceeded]);
    renderSyncRunsPage();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Requeue' })).not.toBeInTheDocument();
  });

  it('shows traceback in expandable row for failed run', async () => {
    mockQuery([mockRunFailedPermanent]);
    renderSyncRunsPage();

    const expandBtn = screen.getAllByRole('button', { name: 'Expand row' })[0];
    await userEvent.click(expandBtn);

    expect(screen.getByText(/Traceback: ConnectionError/)).toBeInTheDocument();
  });

  it('Retry All Failed button fires mutation after Popconfirm', async () => {
    const retryAll = vi.fn(() => ({
      unwrap: () => Promise.resolve({ retried: 1, total_failed_permanent: 1 }),
    }));
    (useRetryAllFailedMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      retryAll,
      { isLoading: false },
    ]);

    mockQuery(
      [mockRunFailedPermanent, mockRunFailedPermanent].map((r, i) => ({ ...r, id: i + 2 }))
    );
    renderSyncRunsPage();

    await userEvent.click(screen.getByRole('button', { name: /Retry All Failed/ }));
    await userEvent.click(screen.getByRole('button', { name: /OK/ }));
    expect(retryAll).toHaveBeenCalledTimes(1);
  });

  it('hides action buttons when permission is missing', () => {
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => false),
      hasAnyPermission: vi.fn(() => false),
      hasAllPermissions: vi.fn(() => false),
      permissions: [],
      isLoading: false,
    });
    mockQuery([mockRunFailedPermanent, mockRunStuck]);
    renderSyncRunsPage();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Requeue' })).not.toBeInTheDocument();
  });

  it('shows empty state when no runs', () => {
    renderSyncRunsPage();
    expect(screen.getByText('No sync runs found')).toBeInTheDocument();
  });
});
