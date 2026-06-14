/**
 * @file Admin.test.tsx
 * @description Integration tests for the Admin Users page (create, toggle active, delete)
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router, antd
 * @relatedFiles ../../pages/Admin/index.tsx, ../../store/api.ts, ../../hooks/usePermissions.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
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
    useListUsersQuery: vi.fn(),
    useCreateUserMutation: vi.fn(),
    useUpdateUserMutation: vi.fn(),
    useDeleteUserMutation: vi.fn(),
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
          <App>
            <AdminPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AdminPage (Users)', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default: user has all permissions
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    // Default: empty users list
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
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
  });

  // -----------------------------------------------------------------------
  // Test 1: Page renders with heading and description
  // -----------------------------------------------------------------------
  it('renders Users heading and description', () => {
    renderAdminPage();

    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Manage user accounts for the BigBug platform.')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Shows User Management section and Add User button
  // -----------------------------------------------------------------------
  it('shows User Management heading and Add User button', () => {
    renderAdminPage();

    expect(screen.getByText('User Management')).toBeInTheDocument();
    expect(screen.getByText('Add User')).toBeInTheDocument();
    // antd Table renders even with empty data (shows empty state)
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Shows table columns
  // -----------------------------------------------------------------------
  it('shows user table columns', () => {
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockUser1],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    // antd Table renders column headers as <th>
    expect(screen.getByText('Username')).toBeInTheDocument();
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Roles')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: Displays user data in the table
  // -----------------------------------------------------------------------
  it('displays user data in the table', () => {
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockUser1, mockUser2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    // getAllByText — 'admin' appears both as username <strong> and role <Tag>
    expect(screen.getAllByText('admin').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('admin@bigbug.dev')).toBeInTheDocument();
    expect(screen.getAllByText('operator').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('operator@bigbug.dev')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Shows empty state
  // -----------------------------------------------------------------------
  it('shows "No users found" when user list is empty', () => {
    renderAdminPage();
    expect(screen.getByText('No users found')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 6: Opens Add User dialog when button is clicked
  // -----------------------------------------------------------------------
  it('opens Add User dialog when button is clicked', async () => {
    renderAdminPage();

    const addButton = screen.getByText('Add User');
    await userEvent.click(addButton);

    // antd Modal has role="dialog"
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText('Add User')).toBeInTheDocument();

    // Form fields — use placeholders since antd Input has no label
    expect(within(dialog).getByPlaceholderText('Username')).toBeInTheDocument();
    expect(within(dialog).getByPlaceholderText('Email')).toBeInTheDocument();
    expect(within(dialog).getByPlaceholderText('Password')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 7: Toggle active switch is present for each user
  // -----------------------------------------------------------------------
  it('shows Active toggle switch for users', () => {
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockUser1],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    // antd Switch renders as role="switch"
    const switches = screen.getAllByRole('switch');
    expect(switches.length).toBeGreaterThanOrEqual(1);
  });

  // -----------------------------------------------------------------------
  // Test 8: Delete button is present for each user
  // -----------------------------------------------------------------------
  it('shows Delete button for users', () => {
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockUser1],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderAdminPage();

    // DeleteOutlined icon button should be in the table row
    const rows = document.querySelectorAll('.ant-table-row');
    expect(rows.length).toBe(1);
    const deleteBtn = rows[0].querySelector('.anticon-delete');
    expect(deleteBtn).toBeTruthy();
  });

  // -----------------------------------------------------------------------
  // Test 9: Smoke test — renders without crashing
  // -----------------------------------------------------------------------
  it('renders without crashing (smoke test)', () => {
    const { container } = renderAdminPage();
    expect(container).toBeTruthy();
  });
});
