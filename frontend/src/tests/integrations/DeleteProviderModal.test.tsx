/**
 * @file DeleteProviderModal.test.tsx
 * @description Integration tests for the provider delete confirmation modal.
 * @dependencies Vitest, @testing-library/react
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App } from 'antd';

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetProviderUsageQuery: vi.fn(),
    useDeleteProviderMutation: vi.fn(),
  };
});

import { api } from '../../store/api';
import { useGetProviderUsageQuery, useDeleteProviderMutation } from '../../store/api';
import { DeleteProviderModal } from '../../pages/Settings/Providers/DeleteProviderModal';
import type { ResourceProvider } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function mockProvider(overrides: Partial<ResourceProvider> = {}): ResourceProvider {
  return {
    id: 1,
    domain: 'git',
    subtype: 'github',
    category: 'private',
    direction: 'external',
    name: 'github-main',
    label: 'GitHub',
    description: null,
    base_url: null,
    config: {},
    credential_id: null,
    owner_user_id: 1,
    visibility: 'owner',
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
    ...overrides,
  };
}

describe('DeleteProviderModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useDeleteProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
  });

  it('shows usage warning and disables delete when usage is non-empty', () => {
    (useGetProviderUsageQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { provider_id: 1, usage: [{ resource: 'mirror', count: 2 }] },
      isLoading: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <DeleteProviderModal provider={mockProvider()} onClose={vi.fn()} />
        </App>
      </Provider>
    );
    expect(screen.getByText('Провайдер используется')).toBeInTheDocument();
  });

  it('shows protected warning for protected providers', () => {
    (useGetProviderUsageQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { provider_id: 1, usage: [] },
      isLoading: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <DeleteProviderModal provider={mockProvider({ is_protected: true })} onClose={vi.fn()} />
        </App>
      </Provider>
    );
    expect(screen.getByText('Провайдер защищён и не может быть удалён')).toBeInTheDocument();
  });
});
