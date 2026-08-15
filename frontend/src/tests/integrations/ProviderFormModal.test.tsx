/**
 * @file ProviderFormModal.test.tsx
 * @description Integration tests for the provider create/edit modal.
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
    useGetProviderTypesQuery: vi.fn(),
    useGetCredentialsQuery: vi.fn(),
    useGetTeamsQuery: vi.fn(),
    useCreateProviderMutation: vi.fn(),
    useUpdateProviderMutation: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

import { api } from '../../store/api';
import {
  useGetProviderTypesQuery,
  useGetCredentialsQuery,
  useGetTeamsQuery,
  useCreateProviderMutation,
  useUpdateProviderMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { ProviderFormModal } from '../../pages/Settings/Providers/ProviderFormModal';
import type { ProviderTypeSpec } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

const githubType: ProviderTypeSpec = {
  subtype: 'github',
  domain: 'git',
  label: 'GitHub',
  capabilities: [],
  allowed_categories: ['public', 'private'],
  allowed_directions: ['external'],
  allowed_credential_types: ['github_token'],
  config_schema: {
    type: 'object',
    properties: {
      api_url: { type: 'string' },
      org_blacklist: { type: 'array', items: { type: 'string' } },
    },
    additionalProperties: false,
  },
  oci_compliant: false,
  requires_base_url: false,
};

describe('ProviderFormModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: () => true,
      hasAnyPermission: () => true,
      hasAllPermissions: () => true,
      permissions: [],
    });
    (useGetProviderTypesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [githubType],
      isLoading: false,
      isError: false,
    });
    (useGetCredentialsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    (useGetTeamsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    (useCreateProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
    (useUpdateProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: {} }),
      { isLoading: false },
    ]);
  });

  it('renders subtype selector and label field', () => {
    render(
      <Provider store={createTestStore()}>
        <App>
          <ProviderFormModal open onClose={vi.fn()} />
        </App>
      </Provider>
    );
    expect(screen.getByText('Provider type')).toBeInTheDocument();
    expect(screen.getByText('Label')).toBeInTheDocument();
  });

  it('renders visibility radio options', () => {
    render(
      <Provider store={createTestStore()}>
        <App>
          <ProviderFormModal open onClose={vi.fn()} />
        </App>
      </Provider>
    );
    expect(screen.getByText('Only me')).toBeInTheDocument();
    expect(screen.getByText('Team')).toBeInTheDocument();
  });
});
