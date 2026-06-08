/**
 * @file Pipelines.test.tsx
 * @description Unit tests for the Pipelines page (Pipeline Runs)
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../pages/Pipelines/index.tsx, ../store/api.ts, ../hooks/usePermissions.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
    useGetPipelineRunsQuery: vi.fn(),
    useTriggerPipelineMutation: vi.fn(),
    useCancelPipelineMutation: vi.fn(),
    useRetryPipelineMutation: vi.fn(),
    useGetGitlabInstancesQuery: vi.fn(),
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
  useGetPipelineRunsQuery,
  useTriggerPipelineMutation,
  useCancelPipelineMutation,
  useRetryPipelineMutation,
  useGetGitlabInstancesQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { PipelinesPage } from '../../pages/Pipelines';
import { STATUS_FLAG, type PipelineRun } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockPipelineRun: PipelineRun = {
  id: 1,
  gitlab_instance_id: 1,
  gitlab_project_id: 42,
  gitlab_pipeline_id: 101,
  triggered_by_user_id: 1,
  trigger_type: 'manual',
  ref: 'main',
  variables: {},
  status_flag: STATUS_FLAG.OK,
  status_text: 'Success',
  duration: 120,
  web_url: 'https://gitlab.example.com/pipelines/101',
  created_at: '2026-06-07T12:00:00Z',
  started_at: '2026-06-07T12:00:00Z',
  finished_at: '2026-06-07T12:02:00Z',
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderPipelinesPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <PipelinesPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PipelinesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetPipelineRunsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 50 },
      isLoading: false,
      isError: false,
      error: null,
    });
    (useTriggerPipelineMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useCancelPipelineMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useRetryPipelineMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useGetGitlabInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  // -----------------------------------------------------------------------
  // Test 1: Page renders heading
  // -----------------------------------------------------------------------
  it('renders "Pipeline Runs" heading', () => {
    renderPipelinesPage();
    expect(screen.getByText('Pipeline Runs')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Status filter buttons are present
  // -----------------------------------------------------------------------
  it('renders status filter toggle buttons', () => {
    renderPipelinesPage();

    expect(screen.getByText('All')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Success')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: "Run Pipeline" button is present
  // -----------------------------------------------------------------------
  it('renders "Run Pipeline" button', () => {
    renderPipelinesPage();
    expect(screen.getByText('Run Pipeline')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: Table columns are rendered
  // -----------------------------------------------------------------------
  it('renders table with correct columns', () => {
    (useGetPipelineRunsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [mockPipelineRun], total: 1, page: 1, page_size: 50 },
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPipelinesPage();

    expect(screen.getByText('#ID')).toBeInTheDocument();
    expect(screen.getByText('Project')).toBeInTheDocument();
    expect(screen.getByText('Ref')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();
    expect(screen.getByText('Created')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Pipeline run data is displayed
  // -----------------------------------------------------------------------
  it('displays pipeline run data in the table', () => {
    (useGetPipelineRunsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [mockPipelineRun], total: 1, page: 1, page_size: 50 },
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPipelinesPage();

    // Check pipeline ID
    expect(screen.getByText('#101')).toBeInTheDocument();
    // Check project ID
    expect(screen.getByText('42')).toBeInTheDocument();
    // Check ref
    expect(screen.getByText('main')).toBeInTheDocument();
    // "Success" appears both as toggle button and StatusChip — use getAllByText
    expect(screen.getAllByText('Success').length).toBeGreaterThanOrEqual(2);
  });

  // -----------------------------------------------------------------------
  // Test 6: Empty state message
  // -----------------------------------------------------------------------
  it('shows "No pipeline runs found" when list is empty', () => {
    renderPipelinesPage();
    expect(screen.getByText('No pipeline runs found')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 7: Loading spinner when isLoading
  // -----------------------------------------------------------------------
  it('shows loading spinner when data is loading', () => {
    (useGetPipelineRunsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    const { container } = renderPipelinesPage();
    // antd Spin renders with .ant-spin-spinning class
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Run Pipeline dialog opens
  // -----------------------------------------------------------------------
  it('opens "Run Pipeline" dialog when button is clicked', async () => {
    renderPipelinesPage();

    const runButton = screen.getByText('Run Pipeline');
    await userEvent.click(runButton);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    // "Run Pipeline" appears as button text and dialog title
    expect(screen.getAllByText('Run Pipeline').length).toBeGreaterThanOrEqual(2);
    // antd Select/Input uses placeholder, not label
    expect(screen.getByText('GitLab Instance')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('GitLab Project ID')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 9: Smoke test — renders without crashing
  // -----------------------------------------------------------------------
  it('renders without crashing (smoke test)', () => {
    const { container } = renderPipelinesPage();
    expect(container).toBeTruthy();
  });
});
