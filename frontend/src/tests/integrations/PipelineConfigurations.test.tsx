/**
 * @file PipelineConfigurations.test.tsx
 * @description Integration tests for the Pipeline Configurations page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../pages/Pipelines/Configurations/index.tsx, ../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
    useGetPipelineConfigsQuery: vi.fn(),
    useDeletePipelineConfigMutation: vi.fn(),
    useDuplicatePipelineConfigMutation: vi.fn(),
    useGetProvidersQuery: vi.fn(),
    useGetComponentsQuery: vi.fn(),
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
  useGetPipelineConfigsQuery,
  useDeletePipelineConfigMutation,
  useDuplicatePipelineConfigMutation,
  useGetProvidersQuery,
  useGetComponentsQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import PipelineConfigsPage from '../../pages/Pipelines/Configurations';
import type { PipelineConfig } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockConfig: PipelineConfig = {
  id: 1,
  name: 'Default Mirror Pipeline',
  description: 'Default pipeline for mirroring repositories',
  provider_id: 1,
  ref: 'main',
  default_variables: { DEPLOY_ENV: 'production' },
  is_default: true,
  is_enabled: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T00:00:00Z',
  components: [
    {
      id: 1,
      pipeline_id: 1,
      component_id: 10,
      order: 0,
      overrides: {},
      component: {
        id: 10,
        name: 'mirror-template',
        description: 'Mirror sync template',
        provider_id: 1,
        project_path: 'bigbug/components/mirror-template',
        component_path: 'templates/mirror.yml',
        version: '1.0.0',
        inputs_schema: null,
        is_enabled: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    },
  ],
  provider: {
    id: 1,
    domain: 'git',
    subtype: 'gitlab',
    category: 'system',
    direction: 'internal',
    name: 'gitlab-local',
    label: 'gitlab-local',
    description: null,
    base_url: 'http://gitlab:8080',
    config: {},
    credential_id: null,
    owner_user_id: null,
    visibility: 'public',
    team_id: null,
    team_name: null,
    is_active: true,
    is_default: false,
    is_protected: false,
    verify_ssl: true,
    priority: 0,
    status_flag: 0,
    status_text: 'OK',
    last_checked_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    has_credential: false,
  },
};

const mockConfig2: PipelineConfig = {
  id: 2,
  name: 'Custom Build Pipeline',
  description: null,
  provider_id: null,
  ref: 'develop',
  default_variables: null,
  is_default: false,
  is_enabled: false,
  created_at: '2026-02-01T00:00:00Z',
  updated_at: '2026-02-10T00:00:00Z',
  components: [],
  provider: null,
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <PipelineConfigsPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PipelineConfigsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useDeletePipelineConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
      { isLoading: false },
    ]);
    (useDuplicatePipelineConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
      { isLoading: false },
    ]);
    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useGetComponentsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  // -----------------------------------------------------------------------
  // Test 1: Page heading
  // -----------------------------------------------------------------------
  it('renders the page heading', () => {
    renderPage();
    expect(screen.getByText('Pipeline Configurations')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Create button
  // -----------------------------------------------------------------------
  it('renders "Create Pipeline" button', () => {
    renderPage();
    expect(screen.getByText('Create Pipeline')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Table renders with pipeline configurations
  // -----------------------------------------------------------------------
  it('renders table with pipeline configurations', () => {
    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockConfig, mockConfig2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage();

    expect(screen.getByText('Default Mirror Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Custom Build Pipeline')).toBeInTheDocument();
    expect(screen.getByText('gitlab-local')).toBeInTheDocument();
    // Default badge (also the column header is 'Default')
    const defaultElements = screen.getAllByText('Default');
    expect(defaultElements.length).toBeGreaterThanOrEqual(2);
  });

  // -----------------------------------------------------------------------
  // Test 4: Search filters the table
  // -----------------------------------------------------------------------
  it('filters configurations by search text', async () => {
    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockConfig, mockConfig2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage();

    const searchInput = screen.getByPlaceholderText('Search by name or description');
    await userEvent.type(searchInput, 'Custom');

    expect(screen.getByText('Custom Build Pipeline')).toBeInTheDocument();
    expect(screen.queryByText('Default Mirror Pipeline')).not.toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Opens create modal
  // -----------------------------------------------------------------------
  it('opens create modal when "Create Pipeline" is clicked', async () => {
    renderPage();

    const createButton = screen.getByText('Create Pipeline');
    await userEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText('Create Pipeline Configuration')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test 6: Delete button is present and clickable
  // -----------------------------------------------------------------------
  it('has a delete button that opens popconfirm', async () => {
    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockConfig],
      isLoading: false,
      isError: false,
      error: null,
    });

    const deleteFn = vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() });
    (useDeletePipelineConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      deleteFn,
      { isLoading: false },
    ]);

    renderPage();

    // Find the delete button — it has danger class in Ant Design
    const deleteBtn = document.querySelector('.ant-btn-dangerous');
    expect(deleteBtn).not.toBeNull();
    if (deleteBtn) {
      await userEvent.click(deleteBtn);
      // Popconfirm should appear
      await waitFor(() => {
        expect(screen.getByText(/This action cannot be undone/)).toBeInTheDocument();
      });
    }
  });

  // -----------------------------------------------------------------------
  // Test 7: Loading state
  // -----------------------------------------------------------------------
  it('shows loading spinner while fetching', () => {
    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Empty state
  // -----------------------------------------------------------------------
  it('shows empty state when no configurations exist', () => {
    renderPage();
    expect(screen.getByText('No pipeline configurations')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 9: Duplicate action
  // -----------------------------------------------------------------------
  it('duplicates a pipeline when duplicate button is clicked', async () => {
    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockConfig],
      isLoading: false,
      isError: false,
      error: null,
    });

    const duplicateFn = vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() });
    (useDuplicatePipelineConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      duplicateFn,
      { isLoading: false },
    ]);

    renderPage();

    // Find buttons with CopyOutlined icon
    const copyButtons = screen
      .getAllByRole('button')
      .filter((btn) => btn.querySelector('.anticon-copy'));
    expect(copyButtons.length).toBeGreaterThan(0);
    await userEvent.click(copyButtons[0]);

    await waitFor(() => {
      expect(duplicateFn).toHaveBeenCalledWith({
        id: 1,
        name: 'Default Mirror Pipeline (copy)',
      });
    });
  });
});
