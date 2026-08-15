/**
 * @file AdminTeams.test.tsx
 * @description Integration tests for the Admin Teams page.
 * @dependencies Vitest, @testing-library/react
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App } from 'antd';

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetTeamsQuery: vi.fn(),
    useCreateTeamMutation: vi.fn(),
    useUpdateTeamMutation: vi.fn(),
    useDeleteTeamMutation: vi.fn(),
    useListUsersQuery: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

import { api } from '../../store/api';
import {
  useGetTeamsQuery,
  useCreateTeamMutation,
  useUpdateTeamMutation,
  useDeleteTeamMutation,
  useListUsersQuery,
} from '../../store/api';
import AdminTeams from '../../pages/Admin/Teams';
import { usePermissions } from '../../hooks/usePermissions';
import type { Team } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function mockTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 1,
    name: 'platform',
    description: null,
    owner: { id: 1, username: 'admin' },
    members_count: 2,
    my_role: 'lead',
    ...overrides,
  };
}

describe('AdminTeams', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: () => true,
      hasAnyPermission: () => true,
      hasAllPermissions: () => true,
      permissions: [],
    });
    (useCreateTeamMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
    (useUpdateTeamMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
    (useDeleteTeamMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
    (useListUsersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [{ id: 1, username: 'admin' }],
      isLoading: false,
      isError: false,
    });
  });

  it('renders Teams heading', () => {
    (useGetTeamsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <MemoryRouter>
          <App>
            <AdminTeams />
          </App>
        </MemoryRouter>
      </Provider>
    );
    expect(screen.getByText('Teams')).toBeInTheDocument();
  });

  it('renders team rows with lead and members count', () => {
    (useGetTeamsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockTeam()],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <MemoryRouter>
          <App>
            <AdminTeams />
          </App>
        </MemoryRouter>
      </Provider>
    );
    expect(screen.getByText('platform')).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
  });
});
