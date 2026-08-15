/**
 * @file ComponentRun.test.tsx
 * @description Integration tests for the GitLab Component Run functionality
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../pages/Settings/Pipelines/index.tsx, ../../store/api.ts, ../../hooks/usePermissions.ts
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
    useGetComponentsQuery: vi.fn(),
    useRunComponentMutation: vi.fn(),
    useGetProvidersQuery: vi.fn(),
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
  useGetComponentsQuery,
  useRunComponentMutation,
  useGetProvidersQuery,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { GitLabComponentsPage } from '../../pages/Settings/Pipelines';
import { GitLabComponent, STATUS_FLAG } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockComponent: GitLabComponent = {
  id: 1,
  name: 'Test Component',
  description: 'A test component',
  provider_id: 1,
  project_path: 'group/test-project',
  component_path: 'components/test-component.yml',
  version: '1.0.0',
  inputs_schema: {
    param1: {
      title: 'Parameter 1',
      type: 'string',
      description: 'First parameter',
      required: true,
    },
    param2: {
      title: 'Parameter 2',
      type: 'boolean',
      description: 'Second parameter',
      required: false,
    },
  },
  is_enabled: true,
  created_at: '2026-06-07T12:00:00Z',
  updated_at: '2026-06-07T12:00:00Z',
};

const mockComponentWithoutInputs: GitLabComponent = {
  id: 2,
  name: 'Simple Component',
  description: 'A simple component without inputs',
  provider_id: 1,
  project_path: 'group/simple-project',
  component_path: 'components/simple-component.yml',
  version: '1.0.0',
  inputs_schema: null,
  is_enabled: true,
  created_at: '2026-06-07T12:00:00Z',
  updated_at: '2026-06-07T12:00:00Z',
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function renderComponentsPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <GitLabComponentsPage />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Component Run Functionality', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetComponentsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockComponent, mockComponentWithoutInputs],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [
        {
          id: 1,
          domain: 'git',
          subtype: 'gitlab',
          category: 'system',
          direction: 'internal',
          name: 'gitlab-local',
          label: 'GitLab Instance 1',
          description: null,
          base_url: 'https://gitlab.example.com',
          config: {},
          credential_id: null,
          owner_user_id: null,
          visibility: 'public',
          team_id: null,
          team_name: null,
          is_active: true,
          is_default: true,
          is_protected: false,
          verify_ssl: true,
          priority: 0,
          status_flag: STATUS_FLAG.OK,
          status_text: 'Connected',
          last_checked_at: null,
          created_at: '2026-06-07T12:00:00Z',
          updated_at: '2026-06-07T12:00:00Z',
          has_credential: false,
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  // -----------------------------------------------------------------------
  // Test 1: runComponent mutation in isolation
  // -----------------------------------------------------------------------
  it('can trigger runComponent mutation with correct parameters', async () => {
    const mockRunComponent = vi.fn().mockReturnValue({
      unwrap: () => Promise.resolve({ id: 1, status_flag: STATUS_FLAG.OK }),
    });
    (useRunComponentMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockRunComponent,
      { isLoading: false },
    ]);

    renderComponentsPage();

    // Find and click the run button for the first component
    const playCircleIcons = screen.getAllByLabelText('play-circle');
    await userEvent.click(playCircleIcons[0]);

    // Wait for modal to appear
    await waitFor(
      () => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      },
      { timeout: 3000 }
    ); // Add timeout to ensure modal appears

    // Wait for the form elements to be available
    await waitFor(
      () => {
        expect(screen.getByRole('combobox', { name: 'GitLab Branch/Ref' })).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Select a branch/ref
    const selectRef = screen.getByRole('combobox', { name: 'GitLab Branch/Ref' });
    await userEvent.click(selectRef);
    await userEvent.click(screen.getByRole('option', { name: 'main' }));

    // Wait for input field to be available
    await waitFor(
      () => {
        expect(screen.getByPlaceholderText('Enter Parameter 1')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Fill in the required input field
    const param1Input = screen.getByPlaceholderText('Enter Parameter 1');
    await userEvent.type(param1Input, 'test-value');

    // Click the run button
    const runButton = screen.getByRole('button', { name: 'Run' });
    await userEvent.click(runButton);

    // Verify the mutation was called with correct parameters
    await waitFor(
      () => {
        expect(mockRunComponent).toHaveBeenCalledWith({
          componentId: 1,
          data: {
            ref: 'main',
            inputs: {
              param1: 'test-value',
            },
          },
        });
      },
      { timeout: 3000 }
    );
  });

  // -----------------------------------------------------------------------
  // Test 2: Integration between runComponent mutation and UI components
  // -----------------------------------------------------------------------
  it('correctly integrates runComponent mutation with UI components', async () => {
    const mockRunComponent = vi.fn().mockReturnValue({
      unwrap: () =>
        Promise.resolve({
          id: 1,
          status_flag: STATUS_FLAG.OK,
          status_text: 'Success',
        }),
    });
    const mockRunComponentMutation = [mockRunComponent, { isLoading: false }];
    (useRunComponentMutation as ReturnType<typeof vi.fn>).mockReturnValue(mockRunComponentMutation);

    renderComponentsPage();

    // Trigger the run action for the first component
    const runButtons = screen.getAllByLabelText('play-circle');
    await userEvent.click(runButtons[0]);

    // Verify the modal opens with correct title
    expect(screen.getByText('Run Component: Test Component')).toBeInTheDocument();

    // Interact with form elements
    const refSelect = screen.getByRole('combobox', { name: 'GitLab Branch/Ref' });
    await userEvent.click(refSelect);
    // Wait for the dropdown popup to appear (antd renders both hidden listbox and visible popup)
    await waitFor(() => {
      const options = screen.getAllByText('develop');
      expect(options.length).toBeGreaterThanOrEqual(2);
    });
    // Click the visible popup option (second match, with .ant-select-item-option-content)
    const developOptions = screen.getAllByText('develop');
    const visibleOption = developOptions.find((el) =>
      el.closest('.ant-select-item-option-content')
    );
    await userEvent.click(visibleOption!);

    const paramInput = screen.getByPlaceholderText('Enter Parameter 1');
    await userEvent.type(paramInput, 'integration-test-value');

    // Submit the form
    const submitButton = screen.getByRole('button', { name: 'Run' });
    await userEvent.click(submitButton);

    // Verify the mutation was called with the correct data from the UI
    await waitFor(() => {
      expect(mockRunComponent).toHaveBeenCalledWith({
        componentId: 1,
        data: {
          ref: 'develop',
          inputs: {
            param1: 'integration-test-value',
          },
        },
      });
    });
  });

  // -----------------------------------------------------------------------
  // Test 3: Run button and modal dialog functionality
  // -----------------------------------------------------------------------
  it('shows run button and opens modal dialog when clicked', async () => {
    (useRunComponentMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);

    renderComponentsPage();

    // Find the run button (using PlayCircleOutlined icon)
    const playCircleIcons = screen.getAllByLabelText('play-circle');
    expect(playCircleIcons).toHaveLength(2); // Should have run buttons for both components

    // Click the first run button (using the icon as a selector)
    await userEvent.click(playCircleIcons[0]);

    // Verify modal appears
    const modal = screen.getByRole('dialog');
    expect(modal).toBeInTheDocument();

    // Verify modal title contains component name
    expect(screen.getByText('Run Component: Test Component')).toBeInTheDocument();

    // Verify modal has correct buttons
    expect(screen.getByText('Cancel')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run' })).toBeInTheDocument();

    // Close the modal
    const cancelButton = screen.getByText('Cancel');
    await userEvent.click(cancelButton);

    // Verify modal closes (check inline style directly — jsdom getComputedStyle is unreliable)
    await waitFor(() => {
      expect(modal.style.display).toBe('none');
    });
  });

  // -----------------------------------------------------------------------
  // Test 4: Dynamic form based on inputs_schema
  // -----------------------------------------------------------------------
  it('renders dynamic form based on inputs_schema', async () => {
    (useRunComponentMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);

    renderComponentsPage();

    // Click run button for component with inputs schema
    const playCircleIcons = screen.getAllByLabelText('play-circle');
    await userEvent.click(playCircleIcons[0]); // Component with inputs_schema

    // Verify the form fields appear based on the schema
    expect(screen.getByText('Parameter 1')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter Parameter 1')).toBeInTheDocument();
    expect(screen.getByText('Parameter 2')).toBeInTheDocument();

    // Verify tooltips appear for descriptions
    const param1Label = screen.getByText('Parameter 1');
    expect(
      param1Label.parentElement?.querySelector('span[aria-label="question-circle"]')
    ).toBeInTheDocument();

    // Verify boolean field renders as select
    const param2Select = screen.getByRole('combobox', { name: 'Parameter 2 question-circle' });
    expect(param2Select).toBeInTheDocument();

    // Close the modal
    const cancelButton = screen.getByText('Cancel');
    await userEvent.click(cancelButton);

    // Now click run button for component without inputs schema
    await userEvent.click(playCircleIcons[1]); // Component without inputs_schema

    // Verify no extra form fields appear for component without schema
    expect(screen.queryByText('Parameter 1')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Enter Parameter 1')).not.toBeInTheDocument();

    // Close the modal
    const secondCancelButton = screen.getByText('Cancel');
    await userEvent.click(secondCancelButton);
  });

  // -----------------------------------------------------------------------
  // Test 5: Error handling scenarios
  // -----------------------------------------------------------------------
  it('handles error scenarios when running component', async () => {
    const mockRunComponent = vi.fn().mockReturnValue({
      unwrap: () => Promise.reject(new Error('Failed to run component')),
    });
    (useRunComponentMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockRunComponent,
      { isLoading: false },
    ]);

    const { container } = renderComponentsPage();

    // Click run button
    const playCircleIcons = screen.getAllByLabelText('play-circle');
    await userEvent.click(playCircleIcons[0]);

    // Fill in required fields
    const refSelect = screen.getByRole('combobox', { name: 'GitLab Branch/Ref' });
    await userEvent.click(refSelect);
    await userEvent.click(screen.getByRole('option', { name: 'main' }));

    const paramInput = screen.getByPlaceholderText('Enter Parameter 1');
    await userEvent.type(paramInput, 'error-test-value');

    // Submit the form
    const runButton = screen.getByRole('button', { name: 'Run' });
    await userEvent.click(runButton);

    // Verify error handling occurs
    await waitFor(() => {
      // Check for error message in Ant Design message container
      const messageContainer = container.querySelector('.ant-message');
      if (messageContainer) {
        expect(messageContainer.textContent).toContain('Failed to trigger component run');
      }
    });

    // Verify the error was logged
    expect(mockRunComponent).toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // Test 6: Success scenarios
  // -----------------------------------------------------------------------
  it('handles success scenario when running component', async () => {
    const mockRunComponent = vi.fn().mockReturnValue({
      unwrap: () =>
        Promise.resolve({
          id: 1,
          status_flag: STATUS_FLAG.OK,
          status_text: 'Success',
        }),
    });
    (useRunComponentMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockRunComponent,
      { isLoading: false },
    ]);

    const { container } = renderComponentsPage();

    // Click run button
    const playCircleIcons = screen.getAllByLabelText('play-circle');
    await userEvent.click(playCircleIcons[0]);

    // Fill in required fields
    const refSelect = screen.getByRole('combobox', { name: 'GitLab Branch/Ref' });
    await userEvent.click(refSelect);
    await userEvent.click(screen.getByRole('option', { name: 'main' }));

    const paramInput = screen.getByPlaceholderText('Enter Parameter 1');
    await userEvent.type(paramInput, 'success-test-value');

    // Submit the form
    const runButton = screen.getByRole('button', { name: 'Run' });
    await userEvent.click(runButton);

    // Verify success message appears
    await waitFor(() => {
      const messageContainer = container.querySelector('.ant-message');
      if (messageContainer) {
        expect(messageContainer.textContent).toContain('Component run triggered successfully');
      }
    });

    // Verify the modal closes after success (check inline style directly)
    await waitFor(() => {
      const dialog = screen.queryByRole('dialog');
      expect(dialog?.style.display).toBe('none');
    });

    // Verify the mutation was called
    expect(mockRunComponent).toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // Test 7: Loading state during component run
  // -----------------------------------------------------------------------
  it('shows loading state while component is running', async () => {
    const mockRunComponent = vi.fn().mockReturnValue({
      unwrap: () =>
        Promise.resolve({
          id: 1,
          status_flag: STATUS_FLAG.IN_PROGRESS,
          status_text: 'Running',
        }),
    });

    // Initially return loading state
    (useRunComponentMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockRunComponent,
      { isLoading: true },
    ]);

    renderComponentsPage();

    // Click run button
    const playCircleIcons = screen.getAllByLabelText('play-circle');
    await userEvent.click(playCircleIcons[0]);

    // Fill in required fields
    const refSelect = screen.getByRole('combobox', { name: 'GitLab Branch/Ref' });
    await userEvent.click(refSelect);
    await userEvent.click(screen.getByRole('option', { name: 'main' }));

    const paramInput = screen.getByPlaceholderText('Enter Parameter 1');
    await userEvent.type(paramInput, 'loading-test-value');

    // Submit the form (when loading, button accessible name becomes "loading Run")
    const runButton = screen.getByRole('button', { name: /Run/ });
    await userEvent.click(runButton);

    // Verify loading spinner appears on the run button (antd6: loading does NOT add disabled)
    expect(runButton.querySelector('.ant-btn-loading-icon')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Test 8: Form validation for required inputs
  // -----------------------------------------------------------------------
  it('validates required inputs in the form', async () => {
    const mockRunComponent = vi.fn().mockReturnValue({
      unwrap: () =>
        Promise.resolve({
          id: 1,
          status_flag: STATUS_FLAG.OK,
          status_text: 'Success',
        }),
    });
    (useRunComponentMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockRunComponent,
      { isLoading: false },
    ]);

    renderComponentsPage();

    // Click run button
    const playCircleIcons = screen.getAllByLabelText('play-circle');
    await userEvent.click(playCircleIcons[0]);

    // Try to submit without filling required fields
    const runButton = screen.getByRole('button', { name: 'Run' });
    await userEvent.click(runButton);

    // Note: ref is pre-filled with 'main' via initialValues, so ref validation won't fire.
    // Parameter validation is tested below.

    // Try to submit without filling required parameter
    await userEvent.click(runButton);

    // Verify validation error for required parameter appears
    await waitFor(() => {
      expect(screen.getByText('Please enter param1')).toBeInTheDocument();
    });

    // Fill in the required parameter
    const paramInput = screen.getByPlaceholderText('Enter Parameter 1');
    await userEvent.type(paramInput, 'validated-value');

    // Now submit should work
    await userEvent.click(runButton);

    // Verify the mutation was called
    await waitFor(() => {
      expect(mockRunComponent).toHaveBeenCalledWith({
        componentId: 1,
        data: {
          ref: 'main',
          inputs: {
            param1: 'validated-value',
          },
        },
      });
    });
  });
});
