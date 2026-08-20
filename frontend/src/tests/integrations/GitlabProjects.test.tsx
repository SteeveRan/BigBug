/**
 * @file GitlabProjects.test.tsx
 * @description Integration tests for the GitLab Projects list page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../pages/Pipelines/Projects/index.tsx, ../../store/api.ts
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
    useGetGitlabProjectsQuery: vi.fn(),
    useGetProvidersQuery: vi.fn(),
    useDeleteGitlabProjectMutation: vi.fn(),
    useCreateGitlabProjectMutation: vi.fn(),
    useImportGitlabProjectMutation: vi.fn(),
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
  useGetGitlabProjectsQuery,
  useGetProvidersQuery,
  useDeleteGitlabProjectMutation,
  useCreateGitlabProjectMutation,
  useImportGitlabProjectMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { GitlabProjectsPage } from '../../pages/Pipelines/Projects';
import type { GitlabProject } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockProject: GitlabProject = {
  id: 1,
  name: 'components',
  path: 'components',
  namespace_path: 'bigbug-mirrors',
  full_path: 'bigbug-mirrors/components',
  project_type: 'components',
  visibility: 'owner',
  provider_id: 7,
  external_id: '42',
  web_url: 'https://gitlab.example.com/bigbug-mirrors/components',
  default_branch: 'main',
  gitlab_visibility: 'private',
  description: 'Component templates',
  owner_user_id: 1,
  team_id: null,
  status_flag: 0,
  status_text: 'OK',
  last_synced_at: '2026-08-20T00:00:00Z',
  is_deleted: false,
  deleted_at: null,
  created_at: '2026-08-20T00:00:00Z',
  updated_at: '2026-08-20T00:00:00Z',
};

const mockPipelinesProject: GitlabProject = {
  ...mockProject,
  id: 2,
  name: 'pipelines',
  path: 'pipelines',
  full_path: 'bigbug-mirrors/pipelines',
  project_type: 'pipelines',
};

const mockProvider = {
  id: 7,
  domain: 'git',
  subtype: 'gitlab',
  category: 'system',
  direction: 'internal',
  name: 'gitlab-local',
  label: 'gitlab-local',
  description: null,
  base_url: 'https://gitlab.example.com',
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
            <GitlabProjectsPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('GitlabProjectsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetGitlabProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockProvider],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useDeleteGitlabProjectMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
      { isLoading: false },
    ]);
    (useCreateGitlabProjectMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
      { isLoading: false },
    ]);
    (useImportGitlabProjectMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
      { isLoading: false },
    ]);
  });

  it('renders the page heading', () => {
    renderPage();
    expect(screen.getByText('GitLab Projects')).toBeInTheDocument();
  });

  it('renders Create Project button', () => {
    renderPage();
    expect(screen.getByText('Create Project')).toBeInTheDocument();
  });

  it('renders table with projects and type tags', () => {
    (useGetGitlabProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockProject, mockPipelinesProject],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage();

    expect(screen.getByText('components')).toBeInTheDocument();
    expect(screen.getByText('pipelines')).toBeInTheDocument();
    // Type tags (also appear as project names, so use getAllByText)
    expect(screen.getAllByText('Components').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Pipelines').length).toBeGreaterThanOrEqual(1);
  });

  it('shows empty state when no projects exist', () => {
    renderPage();
    expect(screen.getByText('No GitLab projects')).toBeInTheDocument();
  });

  it('shows error alert when list fails', () => {
    (useGetGitlabProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: null,
    });

    renderPage();
    expect(screen.getByText('Failed to load GitLab projects')).toBeInTheDocument();
  });

  it('opens create modal when Create Project is clicked', async () => {
    renderPage();

    await userEvent.click(screen.getByText('Create Project'));

    await waitFor(() => {
      expect(screen.getByText('Create GitLab Project')).toBeInTheDocument();
    });
  });

  it('shows loading spinner while fetching', () => {
    (useGetGitlabProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  it('deletes a project via delete action', async () => {
    const deleteFn = vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() });
    (useDeleteGitlabProjectMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      deleteFn,
      { isLoading: false },
    ]);
    (useGetGitlabProjectsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockProject],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage();

    const deleteBtn = document.querySelector('.ant-btn-dangerous');
    expect(deleteBtn).not.toBeNull();
    if (deleteBtn) {
      await userEvent.click(deleteBtn);
      await waitFor(() => {
        expect(screen.getByText(/This removes the local record/)).toBeInTheDocument();
      });
    }
  });
});
