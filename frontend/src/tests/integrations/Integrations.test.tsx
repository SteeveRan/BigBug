/**
 * @file Integrations.test.tsx
 * @description Unit tests for the Settings > Integrations page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../pages/Settings/Integrations/index.tsx, ../store/api.ts, ../hooks/usePermissions.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';

// ---------------------------------------------------------------------------
// Mocks — must appear before any imports that use these modules
// ---------------------------------------------------------------------------

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetGitlabInstancesQuery: vi.fn(),
    useCreateGitlabInstanceMutation: vi.fn(),
    useUpdateGitlabInstanceMutation: vi.fn(),
    useDeleteGitlabInstanceMutation: vi.fn(),
    useTestGitlabConnectionMutation: vi.fn(),
    useGetHarborInstancesQuery: vi.fn(),
    useCreateHarborInstanceMutation: vi.fn(),
    useUpdateHarborInstanceMutation: vi.fn(),
    useDeleteHarborInstanceMutation: vi.fn(),
    useTestHarborConnectionMutation: vi.fn(),
    useGetGithubInstancesQuery: vi.fn(),
    useCreateGithubInstanceMutation: vi.fn(),
    useUpdateGithubInstanceMutation: vi.fn(),
    useDeleteGithubInstanceMutation: vi.fn(),
    useTestGithubConnectionMutation: vi.fn(),
    useGetDockerRegistryInstancesQuery: vi.fn(),
    useCreateDockerRegistryInstanceMutation: vi.fn(),
    useUpdateDockerRegistryInstanceMutation: vi.fn(),
    useDeleteDockerRegistryInstanceMutation: vi.fn(),
    useTestDockerRegistryConnectionMutation: vi.fn(),
    useGetHelmRepositoryInstancesQuery: vi.fn(),
    useCreateHelmRepositoryInstanceMutation: vi.fn(),
    useUpdateHelmRepositoryInstanceMutation: vi.fn(),
    useDeleteHelmRepositoryInstanceMutation: vi.fn(),
    useTestHelmRepositoryConnectionMutation: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Imports — executed after vi.mock calls are hoisted
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import {
  useGetGitlabInstancesQuery,
  useCreateGitlabInstanceMutation,
  useUpdateGitlabInstanceMutation,
  useDeleteGitlabInstanceMutation,
  useTestGitlabConnectionMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { SettingsIntegrations } from '../../pages/Settings/Integrations';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockGitlabInstance1 = {
  id: 1,
  name: 'gitlab-prod',
  url: 'https://gitlab.example.com',
  is_default: true,
  is_active: true,
  verify_ssl: true,
  token_expires_at: null,
  status_flag: 0,
  status_text: 'OK',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGitlabInstance2 = {
  id: 2,
  name: 'gitlab-staging',
  url: 'https://gitlab.staging.example.com',
  is_default: false,
  is_active: true,
  verify_ssl: false,
  token_expires_at: null,
  status_flag: 1,
  status_text: 'Failed',
  created_at: '2026-01-02T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(api.middleware),
  });
}

function renderIntegrationsPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <SettingsIntegrations />
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SettingsIntegrations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom does not implement window.confirm — mock it to always return true
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    // Default: user has all permissions
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });
    // Default: empty instances, no loading/error
    (useGetGitlabInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
    // Default mutations
    (useCreateGitlabInstanceMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateGitlabInstanceMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteGitlabInstanceMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useTestGitlabConnectionMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  // -----------------------------------------------------------------------
  // Test 1: Tab rendering
  // -----------------------------------------------------------------------
  it('test_renders_integration_tabs', () => {
    renderIntegrationsPage();

    expect(screen.getByText('GitLab')).toBeInTheDocument();
    expect(screen.getByText('Harbor')).toBeInTheDocument();
    expect(screen.getByText('GitHub')).toBeInTheDocument();
    expect(screen.getByText('Docker Registry')).toBeInTheDocument();
    expect(screen.getByText('Helm Repository')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: GitLab instances list
  // -----------------------------------------------------------------------
  it('test_gitlab_instances_list', () => {
    (useGetGitlabInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGitlabInstance1, mockGitlabInstance2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderIntegrationsPage();

    expect(screen.getByText('gitlab-prod')).toBeInTheDocument();
    expect(screen.getByText('gitlab-staging')).toBeInTheDocument();
    expect(screen.getByText('https://gitlab.example.com')).toBeInTheDocument();
    expect(screen.getByText('https://gitlab.staging.example.com')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Add GitLab instance dialog
  // -----------------------------------------------------------------------
  it('test_add_gitlab_instance_dialog', async () => {
    const mockCreateFn = vi.fn().mockReturnValue({
      unwrap: () =>
        Promise.resolve({
          id: 3,
          name: 'new-gitlab',
          url: 'https://new.gitlab.com',
          status_flag: 4,
        }),
    });
    (useCreateGitlabInstanceMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockCreateFn,
      { isLoading: false },
    ]);

    renderIntegrationsPage();

    // Click "Add Instance" button
    const addButton = screen.getByText('Add Instance');
    await userEvent.click(addButton);

    // Dialog should be visible with "Add GitLab Instance" title
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText('Add GitLab Instance')).toBeInTheDocument();

    // Fill in the form — labels are "Name", "URL", "Token" (MUI appends " *" for required fields)
    const nameInput = screen.getByLabelText(/^Name/);
    const urlInput = screen.getByLabelText(/^URL/);
    const tokenInput = screen.getByLabelText(/^Token/);

    await userEvent.type(nameInput, 'new-gitlab');
    await userEvent.type(urlInput, 'https://new.gitlab.com');
    await userEvent.type(tokenInput, 'new-token');

    // Click Create (not Save)
    const createButton = screen.getByText('Create');
    await userEvent.click(createButton);

    // Verify create was called with correct data
    await waitFor(() => {
      expect(mockCreateFn).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'new-gitlab',
          url: 'https://new.gitlab.com',
          token: 'new-token',
          is_default: false,
        })
      );
    });
  });

  // -----------------------------------------------------------------------
  // Test 4: Edit GitLab instance
  // -----------------------------------------------------------------------
  it('test_edit_gitlab_instance', async () => {
    (useGetGitlabInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGitlabInstance1],
      isLoading: false,
      isError: false,
      error: null,
    });

    const mockUpdateFn = vi.fn().mockReturnValue({
      unwrap: () => Promise.resolve({ ...mockGitlabInstance1, name: 'gitlab-prod-updated' }),
    });
    (useUpdateGitlabInstanceMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockUpdateFn,
      { isLoading: false },
    ]);

    renderIntegrationsPage();

    // Click edit button via its aria-label
    const editButton = screen.getByLabelText('Edit gitlab-prod');
    await userEvent.click(editButton);

    // Dialog should open with "Edit GitLab Instance" title
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText('Edit GitLab Instance')).toBeInTheDocument();

    // Name field should be pre-filled with instance name (label is "Name")
    const nameInput = screen.getByLabelText(/^Name/) as HTMLInputElement;
    expect(nameInput.value).toBe('gitlab-prod');

    // Clear and type a new name
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'gitlab-prod-updated');

    // Click Update (not Save)
    const updateButton = screen.getByText('Update');
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(mockUpdateFn).toHaveBeenCalledWith({
        id: 1,
        data: expect.objectContaining({ name: 'gitlab-prod-updated' }),
      });
    });
  });

  // -----------------------------------------------------------------------
  // Test 5: Delete GitLab instance confirmation
  // -----------------------------------------------------------------------
  it('test_delete_gitlab_instance_confirmation', async () => {
    (useGetGitlabInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGitlabInstance2],
      isLoading: false,
      isError: false,
      error: null,
    });

    const mockDeleteFn = vi.fn().mockReturnValue({
      unwrap: () => Promise.resolve({}),
    });
    (useDeleteGitlabInstanceMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockDeleteFn,
      { isLoading: false },
    ]);

    renderIntegrationsPage();

    // Click delete button via its aria-label
    const deleteButton = screen.getByLabelText('Delete gitlab-staging');
    await userEvent.click(deleteButton);

    // Should call delete with the instance id
    await waitFor(() => {
      expect(mockDeleteFn).toHaveBeenCalledWith(2);
    });
  });

  // -----------------------------------------------------------------------
  // Test 6: Test connection success
  // -----------------------------------------------------------------------
  it('test_test_connection_success', async () => {
    (useGetGitlabInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGitlabInstance1],
      isLoading: false,
      isError: false,
      error: null,
    });

    const mockTestFn = vi.fn().mockReturnValue({
      unwrap: () =>
        Promise.resolve({
          success: true,
          message: 'Connected successfully',
          status_code: 200,
        }),
    });
    (useTestGitlabConnectionMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockTestFn,
      { isLoading: false },
    ]);

    renderIntegrationsPage();

    // Click test connection button via its aria-label
    const testButton = screen.getByLabelText('Test connection to gitlab-prod');
    await userEvent.click(testButton);

    // Wait for the snackbar with success message (just "Connection successful")
    await waitFor(() => {
      expect(screen.getByText('Connection successful')).toBeInTheDocument();
    });

    expect(mockTestFn).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // Test 7: Test connection failure
  // -----------------------------------------------------------------------
  it('test_test_connection_failure', async () => {
    (useGetGitlabInstancesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGitlabInstance1],
      isLoading: false,
      isError: false,
      error: null,
    });

    const mockTestFn = vi.fn().mockReturnValue({
      unwrap: () => Promise.reject(new Error('Connection refused')),
    });
    (useTestGitlabConnectionMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockTestFn,
      { isLoading: false },
    ]);

    renderIntegrationsPage();

    // Click test connection button via its aria-label
    const testButton = screen.getByLabelText('Test connection to gitlab-prod');
    await userEvent.click(testButton);

    // Wait for the snackbar with error message
    await waitFor(() => {
      expect(screen.getByText('Connection test failed')).toBeInTheDocument();
    });

    expect(mockTestFn).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // Test 8: Permission gate (at route level, not in component)
  // -----------------------------------------------------------------------
  it('test_permission_gate', () => {
    // Mock no permissions at all
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => false),
      hasAnyPermission: vi.fn(() => false),
      hasAllPermissions: vi.fn(() => false),
      permissions: [],
      isLoading: false,
    });

    renderIntegrationsPage();

    // The page still renders — permission checking is at the route level
    // (ProtectedRoute), not inside this component. The PageHeading and tabs
    // are always visible regardless of usePermissions return values.
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('GitLab')).toBeInTheDocument();
  });
});
