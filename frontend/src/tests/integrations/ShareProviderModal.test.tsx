/**
 * @file ShareProviderModal.test.tsx
 * @description Integration tests for the ShareProviderModal.
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
    useGetTeamsQuery: vi.fn(),
    useShareProviderMutation: vi.fn(),
  };
});

import { api } from '../../store/api';
import { useGetTeamsQuery, useShareProviderMutation } from '../../store/api';
import { ShareProviderModal } from '../../pages/Settings/Providers/ShareProviderModal';
import type { ResourceProvider, Team } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function mockProvider(): ResourceProvider {
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
  };
}

const team: Team = {
  id: 1,
  name: 'platform',
  description: null,
  owner: { id: 1, username: 'admin' },
  members_count: 2,
  my_role: 'lead',
};

describe('ShareProviderModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useGetTeamsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [team],
      isLoading: false,
      isError: false,
    });
    (useShareProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
  });

  it('renders info alert using title prop', () => {
    render(
      <Provider store={createTestStore()}>
        <App>
          <ShareProviderModal provider={mockProvider()} onClose={vi.fn()} />
        </App>
      </Provider>
    );
    expect(screen.getByText('Провайдер станет виден всем участникам команды')).toBeInTheDocument();
  });
});
