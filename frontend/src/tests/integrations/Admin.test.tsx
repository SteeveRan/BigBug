/**
 * @file Admin.test.tsx
 * @description Unit tests for the Admin page with Users and Roles tabs
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../pages/Admin/index.tsx, ../store/api.ts, ../hooks/usePermissions.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
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
    useListUsersQuery: vi.fn(),
    useCreateUserMutation: vi.fn(),
    useUpdateUserMutation: vi.fn(),
    useDeleteUserMutation: vi.fn(),
    useGetAllRolesQuery: vi.fn(),
    useCreateRoleMutation: vi.fn(),
    useUpdateRoleMutation: vi.fn(),
    useDeleteRoleMutation: vi.fn(),
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
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
  useGetAllRolesQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { AdminPage } from '../../pages/Admin';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
  roles: ['operator'],
};

const mockRoleBuiltin = {
  id: 1,
  name: 'admin',
  description: 'Built-in admin role',
  is_custom: false,
  created_by_user_id: null,
  permissions: [{ id: 1, name: 'mirrors:read', description: null }],
};

const mockRoleCustom = {
  id: 10,
  name: 'dev_lead',
  description: 'Custom role for dev leads',
  is_custom: true,
  created_by_user_id: 1,
  permissions: [
    { id: 1, name: 'mirrors:read', description: null },
    { id: 2, name: 'mirrors:write', description: null },
  ],
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderAdminPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <AdminPage />
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    // Default: user has all permissions
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    // Default: Users tab — empty list
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    // Default: Roles tab — empty list
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    // Default mutations
    (useCreateUserMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateUserMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteUserMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useCreateRoleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateRoleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteRoleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  // -----------------------------------------------------------------------
  // Test 1: Page renders with heading and tabs
  // -----------------------------------------------------------------------
  it('renders Admin heading and Users/Roles tabs', () => {
    renderAdminPage();

    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('Manage users, roles, and permissions for the BigBug platform.')).toBeInTheDocument();

    // Tabs
    const tabList = screen.getByRole('tablist');
    expect(within(tabList).getByText('Users')).toBeInTheDocument();
    expect(within(tabList).getByText('Roles')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Users tab shows user management heading and Add User button
  // -----------------------------------------------------------------------
  it('shows Users tab content with Add User button', () => {
    renderAdminPage();

    expect(screen.getByText('User Management')).toBeInTheDocument();
    expect(screen.getByText('Add User')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Users tab shows table columns
  // -----------------------------------------------------------------------
  it('shows user table columns', () => {
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockUser1],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    expect(screen.getByText('Username')).toBeInTheDocument();
    expect(screen.getByText('Email')).toBeInTheDocument();
    // "Roles" appears both in tab and table column header — use getAllByText
    expect(screen.getAllByText('Roles').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: Users tab displays user data
  // -----------------------------------------------------------------------
  it('displays user data in the table', () => {
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockUser1, mockUser2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    // "admin" appears as username and role chip — use getAllByText
    expect(screen.getAllByText('admin').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('admin@bigbug.dev')).toBeInTheDocument();
    expect(screen.getAllByText('operator').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('operator@bigbug.dev')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Users tab shows empty state
  // -----------------------------------------------------------------------
  it('shows "No users found" when user list is empty', () => {
    renderAdminPage();
    expect(screen.getByText('No users found')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 6: Users tab — Add User dialog
  // -----------------------------------------------------------------------
  it('opens Add User dialog when button is clicked', async () => {
    renderAdminPage();

    const addButton = screen.getByText('Add User');
    await userEvent.click(addButton);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    // "Add User" appears as button text and dialog title — scope to dialog
    expect(within(dialog).getByText('Add User')).toBeInTheDocument();

    // Form fields
    expect(screen.getByLabelText(/^Username/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Email/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password/)).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 7: Switch to Roles tab
  // -----------------------------------------------------------------------
  it('switches to Roles tab and shows Role Management', async () => {
    renderAdminPage();

    const rolesTab = screen.getByRole('tab', { name: 'Roles' });
    await userEvent.click(rolesTab);

    expect(screen.getByText('Role Management')).toBeInTheDocument();
    expect(screen.getByText('Create Role')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Roles tab shows table columns
  // -----------------------------------------------------------------------
  it('shows role table columns', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin, mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    // Navigate to Roles tab
    const rolesTab = screen.getByRole('tab', { name: 'Roles' });
    await userEvent.click(rolesTab);

    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByText('Type')).toBeInTheDocument();
    expect(screen.getByText('Permissions')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 9: Roles tab displays role data with builtin/custom badges
  // -----------------------------------------------------------------------
  it('displays roles with proper type badges', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin, mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    // Navigate to Roles tab
    const rolesTab = screen.getByRole('tab', { name: 'Roles' });
    await userEvent.click(rolesTab);

    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('dev_lead')).toBeInTheDocument();
    expect(screen.getByText('Builtin')).toBeInTheDocument();
    expect(screen.getByText('Custom')).toBeInTheDocument();
    expect(screen.getByText('Built-in admin role')).toBeInTheDocument();
    expect(screen.getByText('Custom role for dev leads')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 10: Roles tab — Builtin roles have locked Edit/Delete buttons
  // -----------------------------------------------------------------------
  it('disables Edit and Delete for builtin roles', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleBuiltin],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    const rolesTab = screen.getByRole('tab', { name: 'Roles' });
    await userEvent.click(rolesTab);

    // Find the row containing "Builtin" badge
    const rows = screen.getAllByRole('row');
    const builtinRow = rows.find((row) => within(row).queryByText('Builtin'));
    expect(builtinRow).toBeTruthy();

    // All IconButtons in the builtin row should be disabled
    const buttons = within(builtinRow!).getAllByRole('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  // -----------------------------------------------------------------------
  // Test 11: Roles tab — Custom roles have enabled Edit/Delete
  // -----------------------------------------------------------------------
  it('enables Edit and Delete for custom roles', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    const rolesTab = screen.getByRole('tab', { name: 'Roles' });
    await userEvent.click(rolesTab);

    // Find the row containing "Custom" badge
    const rows = screen.getAllByRole('row');
    const customRow = rows.find((row) => within(row).queryByText('Custom'));
    expect(customRow).toBeTruthy();

    // All IconButtons in the custom row should be enabled
    const buttons = within(customRow!).getAllByRole('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);
    buttons.forEach((btn) => expect(btn).not.toBeDisabled());
  });

  // -----------------------------------------------------------------------
  // Test 12: Roles tab — Create Role dialog
  // -----------------------------------------------------------------------
  it('opens Create Role dialog', async () => {
    renderAdminPage();

    const rolesTab = screen.getByRole('tab', { name: 'Roles' });
    await userEvent.click(rolesTab);

    const createButton = screen.getByText('Create Role');
    await userEvent.click(createButton);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    // "Create Role" appears as button text and dialog title — scope to dialog
    expect(within(dialog).getByText('Create Role')).toBeInTheDocument();
    // "Permissions" appears as table column header AND dialog subtitle — scope to dialog
    expect(within(dialog).getByText('Permissions')).toBeInTheDocument();

    // Name and Description fields — MUI adds asterisk for required fields
    expect(screen.getByLabelText(/^Name/)).toBeInTheDocument();
    expect(screen.getByLabelText('Description')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 13: Roles tab — Edit Role dialog
  // -----------------------------------------------------------------------
  it('opens Edit Role dialog for custom role', async () => {
    (useGetAllRolesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockRoleCustom],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    const rolesTab = screen.getByRole('tab', { name: 'Roles' });
    await userEvent.click(rolesTab);

    // Find the row containing "Custom" badge, then click the first enabled button
    const rows = screen.getAllByRole('row');
    const customRow = rows.find((row) => within(row).queryByText('Custom'));
    expect(customRow).toBeTruthy();
    const buttons = within(customRow!).getAllByRole('button');
    // First button is Edit (EditIcon), second is Delete (DeleteIcon)
    await userEvent.click(buttons[0]);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText(/Edit Role: dev_lead/)).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 14: Admin page smoke test — renders without crashing
  // -----------------------------------------------------------------------
  it('renders without crashing (smoke test)', () => {
    const { container } = renderAdminPage();
    expect(container).toBeTruthy();
  });
});
