/**
 * @file GitMirroringAddRepositoryModal.test.tsx
 * @description Integration tests for the AddRepositoryModal component
 * @dependencies Vitest, @testing-library/react, Redux Toolkit
 * @relatedFiles ../../pages/GitMirroring/Sources/AddRepositoryModal.tsx, ../../store/api.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
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
    useGetProvidersQuery: vi.fn(),
    useCreateSourceRepositoryMutation: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import { useGetProvidersQuery, useCreateSourceRepositoryMutation } from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { AddRepositoryModal } from '../../pages/GitMirroring/Sources/AddRepositoryModal';
import type { SourceProvider } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockGithubProvider: SourceProvider = {
  id: 1,
  label: 'GitHub',
  provider_type: 'github',
  credential_id: null,
  credential: undefined,
  is_anon: false,
  is_builtin: false,
  status_flag: 0,
  status_text: 'OK',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

interface RenderModalOptions {
  preselectedProviderId?: number;
}

function renderModal(options: RenderModalOptions = {}) {
  const store = createTestStore();
  const onClose = vi.fn();
  const user = userEvent.setup();

  const result = render(
    <Provider store={store}>
      <App>
        <AddRepositoryModal
          open
          onClose={onClose}
          preselectedProviderId={options.preselectedProviderId}
        />
      </App>
    </Provider>
  );

  return { store, onClose, user, ...result };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AddRepositoryModal', () => {
  let mockCreateRepo: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockCreateRepo = vi.fn().mockReturnValue({
      unwrap: () => Promise.resolve({ id: 42 }),
    });

    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: vi.fn(() => true),
      hasAnyPermission: vi.fn(() => true),
      hasAllPermissions: vi.fn(() => true),
      permissions: [],
      isLoading: false,
    });

    (useGetProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockGithubProvider],
      isLoading: false,
      isError: false,
      error: null,
    });

    (useCreateSourceRepositoryMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockCreateRepo,
      { isLoading: false },
    ]);
  });

  // -----------------------------------------------------------------------
  // WP11.1: Renders with default provider_type 'github'
  // -----------------------------------------------------------------------
  it('renders with default provider_type github', () => {
    renderModal();

    // Check the modal title
    expect(screen.getByText('Add Repository')).toBeInTheDocument();

    // Check that the Select has 'github' as the default value
    // The Select renders the selected option label (GitHub) in the trigger
    expect(screen.getByText('GitHub')).toBeInTheDocument();

    // Also verify the Provider Type label is present
    expect(screen.getByText('Provider Type')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // WP11.2: Shows warning when github.com URL with generic type
  // -----------------------------------------------------------------------
  it('shows warning when github.com URL with generic type', async () => {
    const { user } = renderModal();

    // Select 'generic' provider type
    const providerSelect = screen.getByRole('combobox');
    await user.click(providerSelect);

    // Wait for dropdown and select 'Generic Git'
    const genericOption = await screen.findByText('Generic Git');
    await user.click(genericOption);

    // Enter a github.com URL in the clone_url input
    const urlInput = screen.getByPlaceholderText(/git\.example\.com/);
    await user.type(urlInput, 'https://github.com/owner/repo.git');

    // The warning Alert should appear
    await waitFor(() => {
      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
      expect(alert.textContent).toContain('The URL appears to be a GitHub or GitLab repository');
    });
  });

  // -----------------------------------------------------------------------
  // WP11.3: Does NOT show warning when github.com URL with github type
  // -----------------------------------------------------------------------
  it('does not show warning when github.com URL with github type', async () => {
    const { user } = renderModal();

    // Provider type defaults to 'github' — no need to change

    // Enter a github.com URL
    const urlInput = screen.getByPlaceholderText(/git\.example\.com/);
    await user.type(urlInput, 'https://github.com/owner/repo.git');

    // The warning Alert should NOT appear
    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // WP11.4: Does NOT show warning when non-github URL with generic type
  // -----------------------------------------------------------------------
  it('does not show warning when non-github URL with generic type', async () => {
    const { user } = renderModal();

    // Select 'generic' provider type
    const providerSelect = screen.getByRole('combobox');
    await user.click(providerSelect);
    const genericOption = await screen.findByText('Generic Git');
    await user.click(genericOption);

    // Enter a non-github, non-gitlab URL
    const urlInput = screen.getByPlaceholderText(/git\.example\.com/);
    await user.type(urlInput, 'https://example.com/repo.git');

    // The warning Alert should NOT appear
    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // WP11.5: Submits form with correct values
  // -----------------------------------------------------------------------
  it('submits form with correct values', async () => {
    const { user } = renderModal();

    // Select 'gitlab' provider type
    const providerSelect = screen.getByRole('combobox');
    await user.click(providerSelect);
    const gitlabOption = await screen.findByText('GitLab');
    await user.click(gitlabOption);

    // Enter a clone URL
    const urlInput = screen.getByPlaceholderText(/git\.example\.com/);
    await user.type(urlInput, 'https://gitlab.com/group/repo.git');

    // Submit the form
    const addButton = screen.getByText('Add');
    await user.click(addButton);

    // Verify the mutation was called with correct parameters
    await waitFor(() => {
      expect(mockCreateRepo).toHaveBeenCalledWith({
        provider_type: 'gitlab',
        clone_url: 'https://gitlab.com/group/repo.git',
      });
    });
  });

  // -----------------------------------------------------------------------
  // WP11.6: Closes modal after successful submit
  // -----------------------------------------------------------------------
  it('closes modal after successful submission', async () => {
    const { onClose, user } = renderModal();

    // Enter a clone URL
    const urlInput = screen.getByPlaceholderText(/git\.example\.com/);
    await user.type(urlInput, 'https://github.com/owner/repo.git');

    // Submit the form
    const addButton = screen.getByText('Add');
    await user.click(addButton);

    // Modal onClose should be called after successful creation
    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });
});
