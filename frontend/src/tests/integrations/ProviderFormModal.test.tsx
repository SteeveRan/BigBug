/**
 * @file ProviderFormModal.test.tsx
 * @description Integration tests for the provider create/edit modal. Covers the
 *              type Radio.Group (domain), cascading subtype Select (hidden when a
 *              domain has a single subtype), anonymous access switch, inline
 *              credential inputs, exclusion of system-only providers, and edit
 *              mode prefill.
 * @dependencies Vitest, @testing-library/react
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
    useGetTrustStoresQuery: vi.fn(),
    useCreateProviderMutation: vi.fn(),
    useUpdateProviderMutation: vi.fn(),
    useTestProviderMutation: vi.fn(),
    useCreateCredentialMutation: vi.fn(),
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
  useGetTrustStoresQuery,
  useCreateProviderMutation,
  useUpdateProviderMutation,
  useTestProviderMutation,
  useCreateCredentialMutation,
} from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import { ProviderFormModal } from '../../pages/Settings/Providers/ProviderFormModal';
import type { ProviderTypeSpec, ResourceProvider } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function type(
  subtype: ProviderTypeSpec['subtype'],
  domain: ProviderTypeSpec['domain'],
  overrides: Partial<ProviderTypeSpec> = {}
): ProviderTypeSpec {
  return {
    subtype,
    domain,
    label: subtype,
    capabilities: [],
    allowed_categories: ['public', 'private'],
    allowed_directions: ['external'],
    allowed_credential_types: ['https_basic'],
    config_schema: { type: 'object', properties: {}, additionalProperties: false },
    oci_compliant: false,
    requires_base_url: false,
    ...overrides,
  };
}

const githubType = type('github', 'git', {
  label: 'GitHub',
  allowed_credential_types: ['github_token'],
  config_schema: {
    type: 'object',
    properties: { api_url: { type: 'string' } },
    additionalProperties: false,
  },
});

const gitlabType = type('gitlab', 'git', {
  label: 'GitLab',
  allowed_credential_types: ['gitlab_token'],
});

const systemOnlyType = type('harbor', 'docker', {
  label: 'Harbor',
  allowed_categories: ['system'],
});

function provider(overrides: Partial<ResourceProvider> = {}): ResourceProvider {
  return {
    id: 1,
    domain: 'git',
    subtype: 'github',
    category: 'private',
    direction: 'external',
    name: 'github-main',
    label: 'GitHub main',
    description: 'Main GitHub account',
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
    trust_store_id: null,
    has_credential: false,
    ...overrides,
  };
}

function renderModal(props: { open?: boolean; provider?: ResourceProvider } = {}) {
  return render(
    <Provider store={createTestStore()}>
      <App>
        <ProviderFormModal open onClose={vi.fn()} {...props} />
      </App>
    </Provider>
  );
}

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
      data: [githubType, gitlabType],
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
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    (useCreateProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockReturnValue({ unwrap: () => Promise.resolve({ id: 1 }) }),
      { isLoading: false },
    ]);
    (useUpdateProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockReturnValue({ unwrap: () => Promise.resolve({ id: 1 }) }),
      { isLoading: false },
    ]);
    (useTestProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockResolvedValue({ data: { ok: true, status_flag: 0 } }),
      { isLoading: false },
    ]);
    (useCreateCredentialMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn().mockReturnValue({ unwrap: () => Promise.resolve({ id: 99 }) }),
      { isLoading: false },
    ]);
  });

  it('renders type Radio.Group and hides system-only domains', () => {
    (useGetProviderTypesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [githubType, systemOnlyType],
      isLoading: false,
      isError: false,
    });
    renderModal();
    // Domain "Git" is available (non-system subtype), "Docker" is not offered
    // because its only subtype is system-only.
    expect(screen.getByText('Provider type')).toBeInTheDocument();
    expect(screen.getByText('Git')).toBeInTheDocument();
    expect(screen.queryByText('Docker')).not.toBeInTheDocument();
  });

  it('shows a cascading subtype Select when a domain has multiple subtypes', async () => {
    renderModal();
    fireEvent.click(screen.getByText('Git'));
    expect(screen.getByText('Provider subtype')).toBeInTheDocument();
    // Both GitHub and GitLab belong to the selected git domain; options render
    // only after the Select dropdown opens. Target the subtype select by its id.
    fireEvent.mouseDown(document.getElementById('subtype')!);
    await waitFor(() => {
      expect(screen.getByText('GitHub')).toBeInTheDocument();
    });
    expect(screen.getByText('GitLab')).toBeInTheDocument();
  });

  it('hides the subtype Select and auto-selects the sole subtype', () => {
    (useGetProviderTypesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [githubType],
      isLoading: false,
      isError: false,
    });
    renderModal();
    fireEvent.click(screen.getByText('Git'));
    // No "Provider subtype" label, and the github spec's config field renders,
    // proving the sole subtype was auto-selected.
    expect(screen.queryByText('Provider subtype')).not.toBeInTheDocument();
    expect(screen.getByText('Api Url')).toBeInTheDocument();
  });

  it('toggles anonymous access and hides credential fields', () => {
    (useGetProviderTypesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [githubType],
      isLoading: false,
      isError: false,
    });
    renderModal();
    fireEvent.click(screen.getByText('Git'));

    // github has a single allowed credential type → type select hidden, token
    // field labelled "Token" shown.
    expect(screen.getByText('Anonymous access')).toBeInTheDocument();
    expect(screen.getByText('Token')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('switch', { name: /anonymous access/i }));
    expect(screen.queryByText('Token')).not.toBeInTheDocument();
  });

  it('prefills fields when editing an existing provider', () => {
    renderModal({ provider: provider() });
    expect(screen.getByDisplayValue('GitHub main')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Main GitHub account')).toBeInTheDocument();
    // Edit mode shows the read-only provider type tag instead of the Radio.Group.
    expect(screen.queryByText('Provider subtype')).not.toBeInTheDocument();
  });

  it('sends trust_store_id on create when a store is selected', async () => {
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [{ id: 7, name: 'Corp Root CA', description: null }],
      isLoading: false,
      isError: false,
    });
    // Single git subtype → auto-selected without touching the subtype dropdown.
    (useGetProviderTypesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [githubType],
      isLoading: false,
      isError: false,
    });
    renderModal();
    const createProvider = (useCreateProviderMutation as ReturnType<typeof vi.fn>).mock
      .results[0].value[0];
    fireEvent.click(screen.getByText('Git'));
    // Single mocked subtype (github) auto-selects; its config field mounts.
    await screen.findByText('Api Url');
    fireEvent.change(screen.getByPlaceholderText('e.g. GitHub main'), {
      target: { value: 'GH' },
    });
    // github_token credential secret is required in create mode.
    fireEvent.change(screen.getByLabelText('Token'), { target: { value: 'tok' } });
    // Direction Select has no initialValue — pick it explicitly.
    fireEvent.mouseDown(document.getElementById('direction')!);
    fireEvent.click(await screen.findByText('External'));
    fireEvent.mouseDown(document.getElementById('trust_store_id')!);
    fireEvent.click(await screen.findByText('Corp Root CA'));

    fireEvent.click(screen.getByRole('button', { name: /create/i }));
    await waitFor(() => {
      expect(createProvider).toHaveBeenCalled();
    });
    expect(createProvider.mock.calls[0][0].trust_store_id).toBe(7);
  });

  it('clearing the trust store select unbinds it (null in payload)', async () => {
    const updateProvider = vi.fn().mockResolvedValue({ data: {} });
    (useUpdateProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      updateProvider,
      { isLoading: false },
    ]);
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [{ id: 7, name: 'Corp Root CA', description: null }],
      isLoading: false,
      isError: false,
    });
    renderModal({ provider: provider({ trust_store_id: 7 }) });
    // Store name preselected in the select.
    expect(screen.getByText('Corp Root CA')).toBeInTheDocument();
    // Clear it (allowClear) — hover is required for the clear icon in antd.
    fireEvent.mouseEnter(screen.getByText('Corp Root CA').closest('.ant-select')!);
    const clear = document.querySelector('.ant-select-clear')!;
    fireEvent.mouseDown(clear);
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => {
      expect(updateProvider).toHaveBeenCalled();
    });
    expect(updateProvider.mock.calls[0][0].data.trust_store_id).toBeNull();
  });

  it('hides the Trust Store select without trust_stores:read', () => {
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: (p: string) => p !== 'trust_stores:read',
      hasAnyPermission: () => true,
      hasAllPermissions: () => true,
      permissions: [],
    });
    renderModal();
    expect(screen.queryByText('Trust Store')).not.toBeInTheDocument();
  });
});
