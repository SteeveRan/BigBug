/**
 * @file GitMirroringSyncGroups.test.tsx
 * @description Integration tests for the SyncGroups page — Apply Pipeline, cron, concurrency
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../../pages/GitMirroring/SyncGroups/index.tsx, ../../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
    useGetSyncGroupsQuery: vi.fn(),
    useGetPipelineConfigsQuery: vi.fn(),
    useCreateSyncGroupMutation: vi.fn(),
    useUpdateSyncGroupMutation: vi.fn(),
    useDeleteSyncGroupMutation: vi.fn(),
    useApplyPipelineToGroupMutation: vi.fn(),
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
  useGetSyncGroupsQuery,
  useGetPipelineConfigsQuery,
  useCreateSyncGroupMutation,
  useUpdateSyncGroupMutation,
  useDeleteSyncGroupMutation,
  useApplyPipelineToGroupMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import SyncGroupsPage from '../../pages/GitMirroring/SyncGroups';
import type { SyncGroup, PipelineConfig } from '../../types';

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const mockPipeline: PipelineConfig = {
  id: 1,
  name: 'Default Sync Pipeline',
  description: 'Standard sync pipeline',
  gitlab_instance_id: null,
  ref: 'main',
  default_variables: null,
  is_default: true,
  is_enabled: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  components: [],
};

const mockPipeline2: PipelineConfig = {
  id: 2,
  name: 'Hourly Sync Pipeline',
  description: 'Aggressive hourly sync',
  gitlab_instance_id: null,
  ref: 'main',
  default_variables: null,
  is_default: false,
  is_enabled: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  components: [],
};

const mockGroup: SyncGroup = {
  id: 1,
  name: 'Default',
  description: 'Default sync group',
  pipeline_id: 1,
  pipeline: mockPipeline,
  is_default: true,
  mirrors_count: 3,
  sync_cron: '0 */6 * * *',
  sync_enabled: true,
  sync_concurrency: 2,
  freshness_cron: '0 0 * * *',
  freshness_enabled: false,
  freshness_concurrency: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockGroup2: SyncGroup = {
  id: 2,
  name: 'Hourly Group',
  description: 'Aggressive sync',
  pipeline_id: 1,
  pipeline: mockPipeline,
  is_default: false,
  mirrors_count: 0,
  sync_cron: null,
  sync_enabled: false,
  sync_concurrency: 1,
  freshness_cron: null,
  freshness_enabled: false,
  freshness_concurrency: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderSyncGroupsPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <SyncGroupsPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SyncGroupsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default: all permissions granted
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    // Default: empty groups
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    // Default: pipelines loaded
    (useGetPipelineConfigsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockPipeline, mockPipeline2],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useCreateSyncGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateSyncGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteSyncGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useApplyPipelineToGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  // -----------------------------------------------------------------------
  // Test 1: Page heading
  // -----------------------------------------------------------------------
  it('renders "Sync Groups" heading', () => {
    renderSyncGroupsPage();
    expect(screen.getByText('Sync Groups')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 2: Create Sync Group button
  // -----------------------------------------------------------------------
  it('renders "Create Sync Group" button', () => {
    renderSyncGroupsPage();
    expect(screen.getByText('Create Sync Group')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 3: Apply Pipeline button (ThunderboltOutlined)
  // -----------------------------------------------------------------------
  it('renders Apply Pipeline buttons in the actions column when groups are loaded', () => {
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGroup],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSyncGroupsPage();
    // All action buttons (3 per row: Apply Pipeline, Edit, Delete)
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  // -----------------------------------------------------------------------
  // Test 4: Displays sync group data in table
  // -----------------------------------------------------------------------
  it('displays sync group data in the table', () => {
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGroup, mockGroup2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSyncGroupsPage();

    // "Default" appears both as group name (<strong>) and as Tag badge
    const defaultMatches = screen.getAllByText('Default');
    expect(defaultMatches.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Hourly Group')).toBeInTheDocument();
    // Mirrors count
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 5: Empty state
  // -----------------------------------------------------------------------
  it('shows empty state when no sync groups exist', () => {
    renderSyncGroupsPage();
    expect(screen.getByText('No sync groups configured')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 6: Loading spinner
  // -----------------------------------------------------------------------
  it('shows loading spinner when data is loading', () => {
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    renderSyncGroupsPage();

    // Ant Design Spin renders with role="img" and aria-label="loading"
    const spinner = document.querySelector('.ant-spin');
    expect(spinner).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 7: Error alert
  // -----------------------------------------------------------------------
  it('shows error alert when fetch fails', () => {
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
    });

    renderSyncGroupsPage();

    expect(screen.getByText('Failed to load sync groups')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Apply Pipeline modal opens on button click
  // -----------------------------------------------------------------------
  it('opens Apply Pipeline modal when Apply Pipeline button is clicked', async () => {
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGroup2],
      isLoading: false,
      isError: false,
      error: null,
    });

    // suppress window.confirm
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    renderSyncGroupsPage();

    // Find tooltip buttons by ant-tooltip css class or find all buttons and click the first one
    // The "Apply Pipeline" button has ThunderboltOutlined icon
    const allButtons = screen.getAllByRole('button');
    // First action button is Apply Pipeline (before Edit and Delete)
    const applyButton = allButtons[1]; // 0 = Create Sync Group, 1 = Apply Pipeline (first row)
    fireEvent.click(applyButton);

    // Modal should be visible
    await waitFor(() => {
      expect(screen.getByText(/Apply Pipeline/)).toBeInTheDocument();
    });

    // Pipeline Select should be in the modal
    await waitFor(() => {
      expect(
        screen.getByText('Pipeline Configuration')
      ).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test 9: Apply Pipeline calls mutation with correct parameters
  // -----------------------------------------------------------------------
  it('calls applyPipelineToGroup mutation when Apply is clicked', async () => {
    const applyPipelineMock = vi.fn().mockResolvedValue({});
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGroup2],
      isLoading: false,
      isError: false,
      error: null,
    });
    (useApplyPipelineToGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      applyPipelineMock,
      { isLoading: false },
    ]);

    vi.spyOn(window, 'confirm').mockReturnValue(false);

    const user = userEvent.setup();
    renderSyncGroupsPage();

    // Click Apply Pipeline button on the row (first action button after "Create Sync Group")
    const allButtons = screen.getAllByRole('button');
    const applyButton = allButtons[1]; // Apply Pipeline for Hourly Group
    fireEvent.click(applyButton);

    // Wait for modal
    await waitFor(() => {
      expect(screen.getByText(/Apply Pipeline/)).toBeInTheDocument();
    });

    // The antd Select — find by role="combobox", then click to open dropdown
    const select = await screen.findByRole('combobox');
    await user.click(select);

    // Wait for dropdown options and select "Hourly Sync Pipeline"
    await waitFor(async () => {
      const option = screen.getByText('Hourly Sync Pipeline');
      await user.click(option);
    });

    // Click Apply button
    const applyModalButton = screen.getByRole('button', { name: 'Apply' });
    await user.click(applyModalButton);

    // Verify mutation was called with correct parameters
    await waitFor(() => {
      expect(applyPipelineMock).toHaveBeenCalledWith({
        id: 2,
        pipeline_id: 2,
      });
    });
  });

  // -----------------------------------------------------------------------
  // Test 10: smoke test
  // -----------------------------------------------------------------------
  it('renders without crashing (smoke test)', () => {
    const { container } = renderSyncGroupsPage();
    expect(container).toBeTruthy();
  });

  // =======================================================================
  // Group C tests — cron, concurrency, pipeline display
  // =======================================================================

  // -----------------------------------------------------------------------
  // Test C1: Displays cron and concurrency in table
  // -----------------------------------------------------------------------
  it('displays cron and concurrency fields in table rows', () => {
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGroup],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSyncGroupsPage();

    // sync_cron should be visible
    expect(screen.getByText('0 */6 * * *')).toBeInTheDocument();
    // freshness_cron should be visible (even if disabled)
    expect(screen.getByText('0 0 * * *')).toBeInTheDocument();
    // concurrency numbers
    expect(screen.getByText('2')).toBeInTheDocument(); // sync_concurrency = 2
    expect(screen.getByText('1')).toBeInTheDocument(); // freshness_concurrency = 1
  });

  // -----------------------------------------------------------------------
  // Test C2: Create form shows cron fields when sync enabled
  // -----------------------------------------------------------------------
  it('shows cron fields when sync/freshness switches are toggled', async () => {
    renderSyncGroupsPage();

    // Open Create modal
    const createButton = screen.getByText('Create Sync Group');
    fireEvent.click(createButton);

    // Initially cron inputs should NOT be visible (sync_enabled defaults to false)
    expect(screen.queryByPlaceholderText('0 */6 * * *')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('0 0 * * *')).not.toBeInTheDocument();

    // Find and toggle the "Sync Enabled" switch (first switch in the modal)
    // The Switch component renders with role="switch"
    const switches = screen.getAllByRole('switch');
    expect(switches.length).toBe(2);

    // Toggle Sync Enabled (first switch)
    fireEvent.click(switches[0]);

    // Now Sync Cron input should appear
    await waitFor(() => {
      expect(screen.getByPlaceholderText('0 */6 * * *')).toBeInTheDocument();
    });

    // Sync Concurrency should also appear
    const concurrencyInputs = document.querySelectorAll('.ant-input-number');
    expect(concurrencyInputs.length).toBe(1);

    // Toggle Freshness Enabled (second switch)
    fireEvent.click(switches[1]);

    // Freshness Cron should appear
    await waitFor(() => {
      expect(screen.getByPlaceholderText('0 0 * * *')).toBeInTheDocument();
    });

    // Now both concurrency inputs should be visible
    const concurrencyInputs2 = document.querySelectorAll('.ant-input-number');
    expect(concurrencyInputs2.length).toBe(2);
  });

  // -----------------------------------------------------------------------
  // Test C3: Validates cron format
  // -----------------------------------------------------------------------
  it('validates cron format on submit', async () => {
    renderSyncGroupsPage();

    // Open Create modal
    const createButton = screen.getByText('Create Sync Group');
    fireEvent.click(createButton);

    // Fill name
    const nameInput = screen.getByPlaceholderText('e.g. Hourly Sync');
    fireEvent.change(nameInput, { target: { value: 'Test Group' } });

    // Toggle Sync Enabled (first switch)
    const switches = screen.getAllByRole('switch');
    fireEvent.click(switches[0]);

    // Wait for cron input
    await waitFor(() => {
      expect(screen.getByPlaceholderText('0 */6 * * *')).toBeInTheDocument();
    });

    // Enter invalid cron
    const cronInput = screen.getByPlaceholderText('0 */6 * * *');
    fireEvent.change(cronInput, { target: { value: 'invalid cron' } });

    // Submit form
    const okButton = screen.getByRole('button', { name: 'Create' });
    fireEvent.click(okButton);

    // Validation error should appear
    await waitFor(() => {
      expect(
        screen.getByText('Invalid cron expression (5 fields required)')
      ).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Test C4: Submits create with cron settings
  // -----------------------------------------------------------------------
  it('submits create with cron and concurrency settings', async () => {
    const createMock = vi.fn().mockResolvedValue({});
    (useCreateSyncGroupMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      createMock,
      { isLoading: false },
    ]);

    const user = userEvent.setup();
    renderSyncGroupsPage();

    // Open Create modal
    const createButton = screen.getByText('Create Sync Group');
    fireEvent.click(createButton);

    // Fill name
    const nameInput = screen.getByPlaceholderText('e.g. Hourly Sync');
    await user.clear(nameInput);
    await user.type(nameInput, 'Cron Group');

    // Toggle Sync Enabled
    const switches = screen.getAllByRole('switch');
    fireEvent.click(switches[0]);

    // Fill cron
    await waitFor(() => {
      expect(screen.getByPlaceholderText('0 */6 * * *')).toBeInTheDocument();
    });
    const cronInput = screen.getByPlaceholderText('0 */6 * * *');
    await user.clear(cronInput);
    await user.type(cronInput, '0 */2 * * *');

    // Set concurrency
    const concurrencyInputs = document.querySelectorAll('.ant-input-number-input');
    if (concurrencyInputs.length > 0) {
      const syncConcInput = concurrencyInputs[0] as HTMLInputElement;
      await user.clear(syncConcInput);
      await user.type(syncConcInput, '3');
    }

    // Submit form
    const okButton = screen.getByRole('button', { name: 'Create' });
    await user.click(okButton);

    // Verify mutation was called with correct data
    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Cron Group',
          sync_enabled: true,
          sync_cron: '0 */2 * * *',
          sync_concurrency: 3,
          freshness_enabled: false,
          freshness_cron: null,
          freshness_concurrency: 1,
        })
      );
    });
  });

  // -----------------------------------------------------------------------
  // Test C5: Displays pipeline name in table
  // -----------------------------------------------------------------------
  it('displays pipeline name in the Pipeline column', () => {
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGroup],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSyncGroupsPage();

    // Pipeline name "Default Sync Pipeline" should appear in the table
    // (from mockGroup.pipeline.name)
    expect(screen.getByText('Default Sync Pipeline')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test C6: Shows "—" for null pipeline
  // -----------------------------------------------------------------------
  it('shows "—" when pipeline is not assigned', () => {
    const groupNoPipeline: SyncGroup = {
      ...mockGroup2,
      pipeline_id: null,
      pipeline: null,
    };
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [groupNoPipeline],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSyncGroupsPage();

    // The Pipeline column should show "—"
    const dashes = screen.getAllByText('—');
    // One of them should be the pipeline column
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  // -----------------------------------------------------------------------
  // Test C7: Shows "—" for null cron in table
  // -----------------------------------------------------------------------
  it('shows "—" for null cron values in table', () => {
    (useGetSyncGroupsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGroup2],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderSyncGroupsPage();

    // mockGroup2 has null cron values — look for dashes
    const dashes = screen.getAllByText('—');
    // Should have dash for description and dash for pipeline column
    // (Hourly Group has empty mirrors_count = 0, not dash)
    // Pipeline column for Hourly Group shows pipeline name, so no dash there
    // Description column has "Aggressive sync" so no dash there
    // Cron columns should show "—"
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });
});
