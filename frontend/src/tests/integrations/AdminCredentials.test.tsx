/**
 * @file AdminCredentials.test.tsx
 * @description Integration tests for the Admin Credentials page.
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
    useGetCredentialsQuery: vi.fn(),
    useCreateCredentialMutation: vi.fn(),
    useUpdateCredentialMutation: vi.fn(),
    useDeleteCredentialMutation: vi.fn(),
    useTestCredentialMutation: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

import { api } from '../../store/api';
import {
  useGetCredentialsQuery,
  useCreateCredentialMutation,
  useUpdateCredentialMutation,
  useDeleteCredentialMutation,
  useTestCredentialMutation,
} from '../../store/api';
import AdminCredentials from '../../pages/Admin/Credentials';
import { usePermissions } from '../../hooks/usePermissions';
import type { CredentialDetail } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function mockCredential(overrides: Partial<CredentialDetail> = {}): CredentialDetail {
  return {
    id: 1,
    name: 'gh-token',
    credential_type: 'github_token',
    provider: 'github',
    username: null,
    ssh_public_key: null,
    base_url: null,
    status_flag: 0,
    status_text: 'OK',
    last_tested_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('AdminCredentials', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: () => true,
      hasAnyPermission: () => true,
      hasAllPermissions: () => true,
      permissions: [],
    });
    (useCreateCredentialMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
    (useUpdateCredentialMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
    (useDeleteCredentialMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
    (useTestCredentialMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
  });

  it('renders Credentials heading', () => {
    (useGetCredentialsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminCredentials />
        </App>
      </Provider>
    );
    expect(screen.getByText('Credentials')).toBeInTheDocument();
  });

  it('renders credential rows', () => {
    (useGetCredentialsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockCredential()],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminCredentials />
        </App>
      </Provider>
    );
    expect(screen.getByText('gh-token')).toBeInTheDocument();
  });

  it('shows error alert on load failure', () => {
    (useGetCredentialsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: true,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminCredentials />
        </App>
      </Provider>
    );
    expect(screen.getByText('Failed to load credentials')).toBeInTheDocument();
  });
});
