/**
 * @file AuditLog.test.tsx
 * @description Unit tests for the Settings > Audit Log page
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../pages/Settings/AuditLog/index.tsx, ../store/api.ts, ../hooks/usePermissions.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetAuditLogsQuery: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import { useGetAuditLogsQuery } from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import AuditLogPage from '../../pages/Settings/AuditLog';
import type { AuditLog } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockAuditLog1: AuditLog = {
  id: 1,
  user_id: 1,
  username: 'admin',
  action: 'create',
  resource_type: 'role',
  resource_id: 10,
  resource_name: 'dev_lead',
  details: { permissions: ['mirrors:read', 'mirrors:write'] },
  ip_address: '127.0.0.1',
  created_at: '2026-06-07T12:00:00Z',
};

const mockAuditLog2: AuditLog = {
  id: 2,
  user_id: 2,
  username: 'operator',
  action: 'delete',
  resource_type: 'mirror',
  resource_id: 5,
  resource_name: 'my-mirror',
  details: null,
  ip_address: '10.0.0.1',
  created_at: '2026-06-07T13:00:00Z',
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderAuditLogPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <AuditLogPage />
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AuditLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetAuditLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    });
  });

  // -----------------------------------------------------------------------
  // Test 1: Page renders heading
  // -----------------------------------------------------------------------
  it('renders "Audit Log" heading', () => {
    renderAuditLogPage();
    expect(screen.getByText('Audit Log')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Filter controls are present
  // -----------------------------------------------------------------------
  it('renders filter controls', () => {
    const { container } = renderAuditLogPage();

    // antd datetime-local inputs have no labels — find by type attribute
    const dateInputs = container.querySelectorAll('input[type="datetime-local"]');
    expect(dateInputs.length).toBe(2);

    // antd Select shows placeholder text when no value is selected
    expect(screen.getByText('Action')).toBeInTheDocument();
    expect(screen.getByText('Resource Type')).toBeInTheDocument();
    expect(screen.getByText('Apply Filters')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Empty state message
  // -----------------------------------------------------------------------
  it('shows "No audit logs found" when items list is empty', () => {
    renderAuditLogPage();
    expect(screen.getByText('No audit logs found')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 4: Table columns are rendered with data
  // -----------------------------------------------------------------------
  it('renders table with correct columns when data is present', () => {
    (useGetAuditLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [mockAuditLog1], total: 1 },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    });

    renderAuditLogPage();

    expect(screen.getByText('Timestamp')).toBeInTheDocument();
    expect(screen.getByText('User')).toBeInTheDocument();
    // "Action" appears both as filter label and column header — use getAllByText
    expect(screen.getAllByText('Action').length).toBeGreaterThanOrEqual(1);
    // "Resource Type" also appears both as filter label and column header
    expect(screen.getAllByText('Resource Type').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Resource Name')).toBeInTheDocument();
    expect(screen.getByText('Details')).toBeInTheDocument();
    expect(screen.getByText('IP Address')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Audit log data is displayed
  // -----------------------------------------------------------------------
  it('displays audit log data in the table', () => {
    (useGetAuditLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [mockAuditLog1, mockAuditLog2], total: 2 },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    });

    renderAuditLogPage();

    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('operator')).toBeInTheDocument();
    expect(screen.getByText('127.0.0.1')).toBeInTheDocument();
    expect(screen.getByText('10.0.0.1')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 6: Action chips with correct labels
  // -----------------------------------------------------------------------
  it('renders action chips with correct labels', () => {
    (useGetAuditLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [mockAuditLog1, mockAuditLog2], total: 2 },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    });

    renderAuditLogPage();

    // Both 'create' and 'delete' action chips should be present
    const createChips = screen.getAllByText('create');
    const deleteChips = screen.getAllByText('delete');
    expect(createChips.length).toBeGreaterThan(0);
    expect(deleteChips.length).toBeGreaterThan(0);
  });

  // -----------------------------------------------------------------------
  // Test 7: "View" button for logs with details
  // -----------------------------------------------------------------------
  it('shows "View" button for logs with details and opens dialog', async () => {
    (useGetAuditLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [mockAuditLog1], total: 1 },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    });

    renderAuditLogPage();

    const viewButton = screen.getByText('View');
    expect(viewButton).toBeInTheDocument();

    await userEvent.click(viewButton);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText('Audit Log Details')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Loading spinner when isLoading
  // -----------------------------------------------------------------------
  it('shows loading spinner when data is loading', () => {
    (useGetAuditLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isFetching: false,
      isError: false,
      error: null,
    });

    const { container } = renderAuditLogPage();
    // antd Spin renders with .ant-spin-spinning class
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 9: Pagination appears when total > page_size
  // -----------------------------------------------------------------------
  it('shows pagination when there are multiple pages', () => {
    (useGetAuditLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [mockAuditLog1], total: 100 },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    });

    const { container } = renderAuditLogPage();

    // antd Pagination renders with .ant-pagination class
    expect(container.querySelector('.ant-pagination')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 10: Smoke test — renders without crashing
  // -----------------------------------------------------------------------
  it('renders without crashing (smoke test)', () => {
    const { container } = renderAuditLogPage();
    expect(container).toBeTruthy();
  });
});
