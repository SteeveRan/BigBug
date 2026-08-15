/**
 * @file SettingsTeams.test.tsx
 * @description Integration tests for "My teams" page.
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
  };
});

import { api } from '../../store/api';
import { useGetTeamsQuery } from '../../store/api';
import SettingsTeams from '../../pages/Settings/Teams';
import type { Team } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

const team: Team = {
  id: 1,
  name: 'platform',
  description: null,
  owner: { id: 1, username: 'admin' },
  members_count: 2,
  my_role: 'lead',
};

describe('SettingsTeams', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders My teams heading', () => {
    (useGetTeamsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <SettingsTeams />
        </App>
      </Provider>
    );
    expect(screen.getByText('My teams')).toBeInTheDocument();
  });

  it('renders teams with role tags', () => {
    (useGetTeamsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [team],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <SettingsTeams />
        </App>
      </Provider>
    );
    expect(screen.getByText('platform')).toBeInTheDocument();
    expect(screen.getAllByText('Lead').length).toBeGreaterThanOrEqual(1);
  });
});
