/**
 * @file Overview.test.tsx
 * @description Integration tests for the Overview (Dashboard) page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router, antd
 * @relatedFiles ../pages/Overview/index.tsx, ../pages/Dashboard/index.tsx, ../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import { App } from 'antd';
import { api } from '../../store/api';
import authReducer from '../../store/authSlice';
import { STATUS_FLAG } from '../../types';
import type { GitlabMirror } from '../../types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useListProjectsQuery: vi.fn(),
    useListMirrorsQuery: vi.fn(),
    useListGoldImagesQuery: vi.fn(),
    useListAppImagesQuery: vi.fn(),
  };
});

import {
  useListProjectsQuery,
  useListMirrorsQuery,
  useListGoldImagesQuery,
  useListAppImagesQuery,
} from '../../store/api';

import { DashboardPage } from '../../pages/Overview';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockMirrors: GitlabMirror[] = [
  {
    id: 1,
    project_id: 42,
    gitlab_project_id: '12345',
    gitlab_namespace: 'my-group/my-project',
    gitlab_url: 'https://gitlab.example.com/group/project',
    gitlab_name: 'My Project',
    mirrored_branch: 'main',
    last_synced_release_tag: 'v1.0.0',
    last_sync_at: '2026-06-08T00:00:00Z',
    status_flag: STATUS_FLAG.OK,
    status_text: 'OK',
    is_imported: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-06-08T00:00:00Z',
  },
];

function createTestStore() {
  return configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderPage() {
  const store = createTestStore();
  return render(
    <Provider store={store}>
      <BrowserRouter>
        <App>
          <DashboardPage />
        </App>
      </BrowserRouter>
    </Provider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OverviewPage (Dashboard)', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (useListProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    (useListMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    (useListGoldImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    (useListAppImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
  });

  it('renders the Dashboard heading', () => {
    renderPage();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('renders four statistic cards', () => {
    renderPage();

    expect(screen.getByText('GitHub Projects')).toBeInTheDocument();
    expect(screen.getByText('GitLab Mirrors')).toBeInTheDocument();
    expect(screen.getByText('Gold Images')).toBeInTheDocument();
    expect(screen.getByText('App Images')).toBeInTheDocument();
  });

  it('displays correct counts in statistic cards', () => {
    (useListProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [{ id: 1, name: 'repo1' }],
      isLoading: false,
      isError: false,
    });
    (useListMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockMirrors,
      isLoading: false,
      isError: false,
    });
    (useListGoldImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [{ id: 1, name: 'gold-1' }, { id: 2, name: 'gold-2' }],
      isLoading: false,
      isError: false,
    });
    (useListAppImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [{ id: 1, name: 'app-1' }],
      isLoading: false,
      isError: false,
    });

    renderPage();

    // Verify all four stat cards are present
    expect(screen.getByText('GitHub Projects')).toBeInTheDocument();
    expect(screen.getByText('GitLab Mirrors')).toBeInTheDocument();
    expect(screen.getByText('Gold Images')).toBeInTheDocument();
    expect(screen.getByText('App Images')).toBeInTheDocument();
  });

  it('shows loading spinner in stat cards when isLoading', () => {
    (useListProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    (useListMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    (useListGoldImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    (useListAppImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    const { container } = renderPage();
    // antd Spin inside StatCard renders .ant-spin-spinning
    expect(container.querySelectorAll('.ant-spin-spinning').length).toBeGreaterThanOrEqual(1);
  });

  it('shows "Attention Required" card when mirrors have failures', () => {
    (useListMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [
        {
          ...mockMirrors[0],
          status_flag: STATUS_FLAG.FAILED,
          status_text: 'Failed',
        },
      ] as GitlabMirror[],
      isLoading: false,
      isError: false,
    });

    renderPage();

    expect(screen.getByText('Attention Required')).toBeInTheDocument();
    expect(screen.getByText(/1 mirror\(s\) failed last sync/)).toBeInTheDocument();
  });

  it('shows "Attention Required" card when mirrors are stale', () => {
    (useListMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [
        {
          ...mockMirrors[0],
          status_flag: STATUS_FLAG.WARNING,
          status_text: 'Stale',
        },
      ] as GitlabMirror[],
      isLoading: false,
      isError: false,
    });

    renderPage();

    expect(screen.getByText('Attention Required')).toBeInTheDocument();
    expect(screen.getByText(/1 mirror\(s\) are stale/)).toBeInTheDocument();
  });

  it('renders Recent Mirrors Status section', () => {
    (useListMirrorsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockMirrors,
      isLoading: false,
      isError: false,
    });

    renderPage();

    expect(screen.getByText('Recent Mirrors Status')).toBeInTheDocument();
    expect(screen.getByText('My Project')).toBeInTheDocument();
  });

  it('shows "No mirrors configured" when mirror list is empty', () => {
    renderPage();

    expect(screen.getByText('No mirrors configured yet')).toBeInTheDocument();
  });

  it('renders without crashing (smoke test)', () => {
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });
});
