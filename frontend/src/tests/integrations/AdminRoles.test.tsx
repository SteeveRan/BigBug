/**
 * @file AdminRoles.test.tsx
 * @description Integration tests for Admin Roles pages (list, create/edit modal, detail with scope, Users tab)
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router, antd
 * @relatedFiles ../../pages/Admin/Roles/index.tsx, ../../pages/Admin/Roles/RoleModal.tsx, ../../pages/Admin/Roles/RoleDetail.tsx, ../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { BrowserRouter, MemoryRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App } from 'antd';

// ---------------------------------------------------------------------------
// Mocks — must appear before any imports that use these modules
// ---------------------------------------------------------------------------

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    // Roles CRUD
    useGetAllRolesQuery: vi.fn(),
    useCreateRoleMutation: vi.fn(),
    useUpdateRoleMutation: vi.fn(),
    useDeleteRoleMutation: vi.fn(),
    // Permissions
    useGetAllPermissionsQuery: vi.fn(),
    // Role Users
    useGetRoleUsersQuery: vi.fn(),
    // Role Scope
    useGetRoleScopeQuery: vi.fn(),
    useAddRoleScopeItemMutation: vi.fn(),
    useSetRoleScopeMutation: vi.fn(),
    useRemoveRoleScopeItemMutation: vi.fn(),
    // Source Groups / Providers / Sync Groups (for RoleDetail)
    useGetProvidersQuery: vi.fn(),
    useGetSourceGroupsQuery: vi.fn(),
    useGetSyncGroupsQuery: vi.fn(),
    useGetProvidersQuery: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...(actual as object),
    useParams: vi.fn(),
  };
});

// ---------------------------------------------------------------------------
// Imports — executed after vi.mock calls are hoisted
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import {
  useGetAllRolesQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
  useGetAllPermissionsQuery,
  useGetRoleUsersQuery,
  useGetRoleScopeQuery,
  useAddRoleScopeItemMutation,
  useSetRoleScopeMutation,
  useRemoveRoleScopeItemMutation,
  useGetProvidersQuery,
  useGetSourceGroupsQuery,
  useGetSyncGroupsQuery,
  useGetProvidersQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { useParams } from 'react-router';
import RolesPage from '../../pages/Admin/Roles';
import RoleDetailPage from '../../pages/Admin/Roles/RoleDetail';

// ---------------------------------------------------------------------------
// Helpers: mock data
// ---------------------------------------------------------------------------

const mockPermissionRead: { id: number; name: string; description: string | null } = {
  id: 1,
  name: 'mirrors:read',
  description: null,
};

const mockPermissionWrite: { id: number; name: string; description: string | null } = {
  id: 2,
  name: 'mirrors:write',
  description: null,
};

const allPermissionsMock = [
  mockPermissionRead,
  mockPermissionWrite,
  { id: 3, name: 'mirrors:delete', description: null },
  { id: 4, name: 'mirrors:sync', description: null },
  { id: 5, name: 'projects:read', description: null },
  { id: 6, name: 'projects:write', description: null },
  { id: 7, name: 'projects:delete', description: null },
  { id: 8, name: 'helm:read', description: null },
  { id: 9, name: 'helm:write', description: null },
  { id: 10, name: 'helm:delete', description: null },
  { id: 11, name: 'helm:sync', description: null },
  { id: 12, name: 'docker:read', description: null },
  { id: 13, name: 'docker:write', description: null },
  { id: 14, name: 'docker:delete', description: null },
  { id: 15, name: 'docker:sync', description: null },
  { id: 16, name: 'gold_images:read', description: null },
  { id: 17, name: 'gold_images:write', description: null },
  { id: 18, name: 'gold_images:delete', description: null },
  { id: 19, name: 'gold_images:build', description: null },
  { id: 20, name: 'app_images:read', description: null },
  { id: 21, name: 'app_images:write', description: null },
  { id: 22, name: 'app_images:delete', description: null },
  { id: 23, name: 'app_images:build', description: null },
  { id: 24, name: 'users:read', description: null },
  { id: 25, name: 'users:write', description: null },
  { id: 26, name: 'users:delete', description: null },
  { id: 27, name: 'roles:read', description: null },
  { id: 28, name: 'roles:write', description: null },
  { id: 29, name: 'roles:delete', description: null },
  { id: 30, name: 'source_groups:read', description: null },
  { id: 31, name: 'source_groups:write', description: null },
  { id: 32, name: 'source_groups:refresh', description: null },
  { id: 33, name: 'sync_groups:read', description: null },
  { id: 34, name: 'sync_groups:write', description: null },
  { id: 35, name: 'sync_groups:delete', description: null },
  { id: 36, name: 'pipelines:read', description: null },
  { id: 37, name: 'pipelines:write', description: null },
  { id: 38, name: 'pipelines:delete', description: null },
  { id: 39, name: 'credentials:read', description: null },
  { id: 40, name: 'credentials:use', description: null },
  { id: 41, name: 'integrations:read', description: null },
  { id: 42, name: 'integrations:write', description: null },
  { id: 43, name: 'oidc:read', description: null },
  { id: 44, name: 'oidc:write', description: null },
  { id: 45, name: 'audit:read', description: null },
  { id: 46, name: 'reports:read', description: null },
];

const mockRoleBuiltin = {
  id: 1,
  name: 'admin',
  description: 'Built-in admin role',
  is_custom: false,
  created_by_user_id: null,
  permissions: [mockPermissionRead],
  users_count: 2,
};

const mockRoleCustom = {
  id: 10,
  name: 'dev_lead',
  description: 'Custom role for dev leads',
  is_custom: true,
  created_by_user_id: 1,
  permissions: [mockPermissionRead, mockPermissionWrite],
  users_count: 5,
};

const mockUser1 = {
  id: 1,
  username: 'admin',
  email: 'admin@bigbug.dev',
  is_active: true,
  roles: ['admin'],
};

const mockUser2 = {
  id: 2,
  username: 'operator',
  email: 'operator@bigbug.dev',
  is_active: true,
  roles: ['admin', 'operator'],
};

// ---------------------------------------------------------------------------
// Helpers: store & render
// ---------------------------------------------------------------------------

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderRolesPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <RolesPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

function renderRoleDetailPage(roleId: string) {
  (useParams as ReturnType<typeof vi.fn>).mockReturnValue({ roleId });
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <MemoryRouter initialEntries={[`/admin/roles/${roleId}`]}>
          <App>
            <RoleDetailPage />
          </App>
        </MemoryRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Common beforeEach setup
// ---------------------------------------------------------------------------

function setupDefaultMocks() {
  vi.clearAllMocks();

  (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
    hasPermission: vi.fn(() => true),
    hasAnyPermission: vi.fn(() => true),
    hasAllPermissions: vi.fn(() => true),
    permissions: [],
    isLoading: false,
  });

  // Default: empty params (overridden in renderRoleDetailPage)
  (useParams as ReturnType<typeof vi.fn>).mockReturnValue({});

  // Default: empty roles list
  (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    error: null,
  });

  // Default mutations
  (useCreateRoleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
    vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
    { isLoading: false },
  ]);
  (useUpdateRoleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
    vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
    { isLoading: false },
  ]);
  (useDeleteRoleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
    vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
    { isLoading: false },
  ]);

  // Default: all permissions available
  (useGetAllPermissionsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: allPermissionsMock,
    isLoading: false,
    isError: false,
    error: null,
  });

  // Default: empty role users
  (useGetRoleUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    error: null,
  });

  // Default: empty role scope
  (useGetRoleScopeQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: null,
    isLoading: false,
    isError: false,
    error: null,
  });

  // Default scope mutations
  (useAddRoleScopeItemMutation as ReturnType<typeof vi.fn>).mockReturnValue([
    vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
    { isLoading: false },
  ]);
  (useSetRoleScopeMutation as ReturnType<typeof vi.fn>).mockReturnValue([
    vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
    { isLoading: false },
  ]);
  (useRemoveRoleScopeItemMutation as ReturnType<typeof vi.fn>).mockReturnValue([
    vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() }),
    { isLoading: false },
  ]);

  // Default: empty source data
  (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    error: null,
  });
  (useGetSourceGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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
  (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    error: null,
  });
}

// ===========================================================================
// Admin Roles List Tests
// ===========================================================================

describe('Admin Roles List', () => {
  beforeEach(() => {
    setupDefaultMocks();
  });

  // -----------------------------------------------------------------------
  // Test 1: Renders page heading and Create Role button
  // -----------------------------------------------------------------------
  it('renders heading and Create Role button', () => {
    renderRolesPage();

    expect(screen.getByText('Roles')).toBeInTheDocument();
    expect(screen.getByText('Create Role')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Renders table columns (including Type column)
  // -----------------------------------------------------------------------
  it('renders table with column headers', () => {
    renderRolesPage();

    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByText('Type')).toBeInTheDocument();
    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Renders table with role data including Type tags
  // -----------------------------------------------------------------------
  it('displays roles with Builtin/Custom Type tags', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin, mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRolesPage();

    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('dev_lead')).toBeInTheDocument();
    expect(screen.getByText('Built-in admin role')).toBeInTheDocument();
    expect(screen.getByText('Custom role for dev leads')).toBeInTheDocument();
    // Type tags
    expect(screen.getByText('Builtin')).toBeInTheDocument();
    expect(screen.getByText('Custom')).toBeInTheDocument();
    // Users count
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: Builtin roles have LockOutlined icon
  // -----------------------------------------------------------------------
  it('shows lock icon for builtin roles', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin],
      isLoading: false,
      isError: false,
      error: null,
    });

    const { container } = renderRolesPage();

    // LockOutlined renders as an icon with class anticon-lock
    const lockIcon = container.querySelector('.anticon-lock');
    expect(lockIcon).toBeTruthy();
    // No edit/delete icons (they should be disabled/hidden for builtin)
  });

  // -----------------------------------------------------------------------
  // Test 5: Custom roles do NOT have LockOutlined icon
  // -----------------------------------------------------------------------
  it('does not show lock icon for custom roles', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    const { container } = renderRolesPage();

    const lockIcon = container.querySelector('.anticon-lock');
    expect(lockIcon).toBeNull();
  });

  // -----------------------------------------------------------------------
  // Test 6: Edit and Delete buttons disabled for builtin roles
  // -----------------------------------------------------------------------
  it('disables Edit and Delete for builtin roles', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRolesPage();

    // All tooltip-wrapped buttons in the builtin table row should be disabled
    const rows = document.querySelectorAll('.ant-table-row');
    expect(rows.length).toBe(1);
    const buttons = rows[0].querySelectorAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  // -----------------------------------------------------------------------
  // Test 7: Edit and Delete buttons enabled for custom roles
  // -----------------------------------------------------------------------
  it('enables Edit and Delete for custom roles', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRolesPage();

    const rows = document.querySelectorAll('.ant-table-row');
    expect(rows.length).toBe(1);
    const buttons = rows[0].querySelectorAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);
    buttons.forEach((btn) => expect(btn).not.toBeDisabled());
  });

  // -----------------------------------------------------------------------
  // Test 8: Shows loading spinner when fetching
  // -----------------------------------------------------------------------
  it('shows loading spinner while fetching', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    const { container } = renderRolesPage();
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 9: Shows error message on API failure
  // -----------------------------------------------------------------------
  it('shows error message on API failure', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
    });

    renderRolesPage();
    expect(screen.getByText('Failed to load roles. Please try again later.')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 10: Shows empty state when no roles
  // -----------------------------------------------------------------------
  it('shows "No roles found" when list is empty', () => {
    renderRolesPage();
    expect(screen.getByText('No roles found')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 11: Smoke test
  // -----------------------------------------------------------------------
  it('renders without crashing', () => {
    const { container } = renderRolesPage();
    expect(container).toBeTruthy();
  });
});

// ===========================================================================
// Admin Role Modal Tests
// ===========================================================================

describe('Admin Role Modal', () => {
  beforeEach(() => {
    setupDefaultMocks();
  });

  // -----------------------------------------------------------------------
  // Test 12: Opens create modal with empty fields
  // -----------------------------------------------------------------------
  it('opens create modal with empty fields', async () => {
    renderRolesPage();

    const createButton = screen.getByText('Create Role');
    await userEvent.click(createButton);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText('Create Role')).toBeInTheDocument();

    // Name and Description fields should be empty
    const nameInput = within(dialog).getByPlaceholderText('e.g. dev_lead');
    expect(nameInput).toHaveValue('');
    const descInput = within(dialog).getByPlaceholderText('Optional description');
    expect(descInput).toHaveValue('');

    // Permissions section is visible
    expect(within(dialog).getByText('Permissions')).toBeInTheDocument();

    // Footer buttons
    expect(within(dialog).getByText('Cancel')).toBeInTheDocument();
    expect(within(dialog).getByText('Create')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 13: Opens edit modal with pre-filled data
  // -----------------------------------------------------------------------
  it('opens edit modal with pre-filled data', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRolesPage();

    // Find the edit button in the row and click it
    const rows = document.querySelectorAll('.ant-table-row');
    expect(rows.length).toBeGreaterThanOrEqual(1);
    const editBtn = rows[0].querySelector('.anticon-edit');
    expect(editBtn).not.toBeNull();
    if (editBtn) {
      await userEvent.click(editBtn);
    }

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText('Edit Role: dev_lead')).toBeInTheDocument();

    // Name should be pre-filled
    const nameInput = within(dialog).getByPlaceholderText('e.g. dev_lead');
    expect(nameInput).toHaveValue('dev_lead');

    // Description pre-filled
    const descInput = within(dialog).getByPlaceholderText('Optional description');
    expect(descInput).toHaveValue('Custom role for dev leads');

    // Footer shows Save instead of Create
    expect(within(dialog).getByText('Save')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 14: Shows validation error for empty name
  // -----------------------------------------------------------------------
  it('shows validation error for empty name on submit', async () => {
    renderRolesPage();

    const createButton = screen.getByText('Create Role');
    await userEvent.click(createButton);

    const dialog = screen.getByRole('dialog');

    // Submit the form without filling name
    const saveButton = within(dialog).getByText('Create');
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText('Role name is required')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test 15: Submits create successfully
  // -----------------------------------------------------------------------
  it('submits create role successfully', async () => {
    const createFn = vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() });
    (useCreateRoleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      createFn,
      { isLoading: false },
    ]);

    renderRolesPage();

    const createButton = screen.getByText('Create Role');
    await userEvent.click(createButton);

    const dialog = screen.getByRole('dialog');

    // Fill name
    const nameInput = within(dialog).getByPlaceholderText('e.g. dev_lead');
    await userEvent.type(nameInput, 'tester');

    // Submit
    const submitBtn = within(dialog).getByText('Create');
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(createFn).toHaveBeenCalledWith({
        name: 'tester',
        description: undefined,
        permission_names: [],
      });
    });
  });

  // -----------------------------------------------------------------------
  // Test 16: Submits update successfully
  // -----------------------------------------------------------------------
  it('submits update role successfully', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    const updateFn = vi.fn().mockReturnValue({ unwrap: () => Promise.resolve() });
    (useUpdateRoleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      updateFn,
      { isLoading: false },
    ]);

    renderRolesPage();

    // Click edit button
    const rows = document.querySelectorAll('.ant-table-row');
    const editBtn = rows[0].querySelector('.anticon-edit');
    if (editBtn) {
      await userEvent.click(editBtn);
    }

    const dialog = screen.getByRole('dialog');

    // Change description
    const descInput = within(dialog).getByPlaceholderText('Optional description');
    await userEvent.clear(descInput);
    await userEvent.type(descInput, 'Updated description');

    // Submit
    const saveBtn = within(dialog).getByText('Save');
    await userEvent.click(saveBtn);

    await waitFor(() => {
      expect(updateFn).toHaveBeenCalledWith({
        id: 10,
        data: {
          name: undefined,
          description: 'Updated description',
          permission_names: ['mirrors:read', 'mirrors:write'],
        },
      });
    });
  });

  // -----------------------------------------------------------------------
  // Test 17: Shows permissions grouped by category
  // -----------------------------------------------------------------------
  it('shows permissions checkboxes grouped by category', async () => {
    renderRolesPage();

    const createButton = screen.getByText('Create Role');
    await userEvent.click(createButton);

    const dialog = screen.getByRole('dialog');

    // Check that permission group cards are present
    // Mirrors group should have its label
    expect(within(dialog).getByText('Mirrors')).toBeInTheDocument();
    // Each group has Select All / Deselect All buttons
    const selectAllButtons = within(dialog).getAllByText('Select All');
    const deselectAllButtons = within(dialog).getAllByText('Deselect All');
    expect(selectAllButtons.length).toBeGreaterThanOrEqual(1);
    expect(deselectAllButtons.length).toBeGreaterThanOrEqual(1);

    // Permission checkboxes with labels like "read → mirrors"
    expect(within(dialog).getByText('read → mirrors')).toBeInTheDocument();
    expect(within(dialog).getByText('write → mirrors')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 18: Select All / Deselect All per group
  // -----------------------------------------------------------------------
  it('Select All selects all permissions in a group', async () => {
    renderRolesPage();

    const createButton = screen.getByText('Create Role');
    await userEvent.click(createButton);

    const dialog = screen.getByRole('dialog');

    // Click the first "Select All" button (Mirrors group)
    const selectAllButtons = within(dialog).getAllByRole('button', { name: 'Select All' });
    await userEvent.click(selectAllButtons[0]);

    // After selecting all, the Select All button should become disabled
    await waitFor(() => {
      expect(selectAllButtons[0]).toBeDisabled();
    });

    // Now click Deselect All for the same group
    const deselectAllButtons = within(dialog).getAllByRole('button', { name: 'Deselect All' });
    await userEvent.click(deselectAllButtons[0]);

    // After deselecting, Deselect All should be disabled
    await waitFor(() => {
      expect(deselectAllButtons[0]).toBeDisabled();
    });
  });

  // -----------------------------------------------------------------------
  // Test 19: Cancel button closes the modal
  // -----------------------------------------------------------------------
  it('closes modal on Cancel click', async () => {
    renderRolesPage();

    const createButton = screen.getByText('Create Role');
    await userEvent.click(createButton);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();

    const cancelBtn = within(dialog).getByText('Cancel');
    await userEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});

// ===========================================================================
// Admin Role Detail Tests
// ===========================================================================

describe('Admin Role Detail', () => {
  beforeEach(() => {
    setupDefaultMocks();
  });

  // -----------------------------------------------------------------------
  // Test 20: Renders role name and description for a valid role
  // -----------------------------------------------------------------------
  it('renders role name and description', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin, mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    expect(screen.getByText('Role: dev_lead')).toBeInTheDocument();
    expect(screen.getByText('Custom role for dev leads')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 21: Shows Back button
  // -----------------------------------------------------------------------
  it('has Back to Roles button', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin, mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    expect(screen.getByText('Back to Roles')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 22: Shows error when role not found
  // -----------------------------------------------------------------------
  it('shows error Alert when role is not found', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('999');

    expect(screen.getByText('Role Not Found')).toBeInTheDocument();
    expect(screen.getByText('Role with ID 999 was not found.')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 23: Shows loading spinner while fetching role
  // -----------------------------------------------------------------------
  it('shows loading spinner while fetching', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    const { container } = renderRoleDetailPage('10');
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 24: Shows Permissions tab with disabled checkboxes
  // -----------------------------------------------------------------------
  it('shows Permissions tab with assigned permissions', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    // Permissions tab should be visible
    expect(screen.getByRole('tab', { name: 'Permissions' })).toBeInTheDocument();

    // Should display the text about permissions
    expect(screen.getByText(/This role has the following permissions/)).toBeInTheDocument();

    // Assigned Permissions card header
    expect(screen.getByText('Assigned Permissions')).toBeInTheDocument();

    // Permission labels for dev_lead (mirrors:read, mirrors:write)
    expect(screen.getByText('read → mirrors')).toBeInTheDocument();
    expect(screen.getByText('write → mirrors')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 25: Shows Users tab with assigned users
  // -----------------------------------------------------------------------
  it('shows Users tab with assigned users', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetRoleUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockUser1, mockUser2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    // Users tab should be visible (default active tab is Permissions)
    const usersTab = screen.getByRole('tab', { name: 'Users' });
    expect(usersTab).toBeInTheDocument();

    // Click the Users tab to render its content
    await userEvent.click(usersTab);

    // Content should show user data (rendered in the tab content area)
    expect(screen.getByText(/Users directly assigned to this role/)).toBeInTheDocument();

    // Users table — use getAllByText because 'admin' and 'operator' appear
    // both as username <strong> and as role <Tag>
    expect(screen.getAllByText('admin').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('admin@bigbug.dev')).toBeInTheDocument();
    expect(screen.getAllByText('operator').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('operator@bigbug.dev')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 26: Users tab shows count in description
  // -----------------------------------------------------------------------
  it('Users tab shows total count of assigned users', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetRoleUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockUser1, mockUser2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    // Default active tab is Permissions — click Users tab first
    const usersTab = screen.getByRole('tab', { name: 'Users' });
    await userEvent.click(usersTab);

    expect(screen.getByText(/\(2 total\)/)).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 27: Users tab shows empty state when no users assigned
  // -----------------------------------------------------------------------
  it('Users tab shows empty state for role with no users', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetRoleUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    // Default active tab is Permissions — click Users tab to render its content
    const usersTab = screen.getByRole('tab', { name: 'Users' });
    await userEvent.click(usersTab);

    expect(screen.getByText('No users assigned to this role')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 28: Shows Source Groups tab
  // -----------------------------------------------------------------------
  it('shows Source Groups tab', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    const sourceGroupsTab = screen.getByRole('tab', { name: 'Source Groups' });
    expect(sourceGroupsTab).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 29: Shows Credentials tab
  // -----------------------------------------------------------------------
  it('shows Credentials tab', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    const credentialsTab = screen.getByRole('tab', { name: 'Credentials' });
    expect(credentialsTab).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 30: Shows Sync Groups tab
  // -----------------------------------------------------------------------
  it('shows Sync Groups tab', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderRoleDetailPage('10');

    const syncGroupsTab = screen.getByRole('tab', { name: 'Sync Groups' });
    expect(syncGroupsTab).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 31: Smoke test — renders without crashing
  // -----------------------------------------------------------------------
  it('renders without crashing', () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    const { container } = renderRoleDetailPage('10');
    expect(container).toBeTruthy();
  });
});
