/**
 * @file AuthenticationSettings.test.tsx
 * @description Integration tests for the Settings > Authentication page (Ant Design).
 *              Covers loading/error states, provider cards rendering (multiple
 *              providers, sort order, enabled badge), edit modal, create, delete
 *              and enable/disable toggle.
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router, antd
 * @relatedFiles ../pages/Settings/Authentication/index.tsx, ../store/api.ts
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
// Mocks — must appear before any imports that use these modules
// ---------------------------------------------------------------------------

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetOidcProvidersQuery: vi.fn(),
    useCreateOidcProviderMutation: vi.fn(),
    useUpdateOidcProviderMutation: vi.fn(),
    useDeleteOidcProviderMutation: vi.fn(),
  };
});

// ---------------------------------------------------------------------------
// Imports — executed after vi.mock calls are hoisted
// ---------------------------------------------------------------------------

import {
  api,
  useGetOidcProvidersQuery,
  useCreateOidcProviderMutation,
  useUpdateOidcProviderMutation,
  useDeleteOidcProviderMutation,
} from '../../store/api';
import { AuthenticationSettings } from '../../pages/Settings/Authentication';
import type { OIDCProvider } from '../../types';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const mockProviderA: OIDCProvider = {
  id: 1,
  name: 'Corporate Keycloak',
  issuer_url: 'https://keycloak.example.com/realms/myrealm',
  client_id: 'bigbug-backend',
  client_secret: '********',
  frontend_client_id: 'bigbug-frontend',
  enabled: true,
  public_url: 'https://auth.example.com',
  role_mapping: {
    'bigbug-admin': 'admin',
    'bigbug-viewer': 'viewer',
  },
  sort_order: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockProviderB: OIDCProvider = {
  ...mockProviderA,
  id: 2,
  name: 'Partner Keycloak',
  issuer_url: 'https://partner.example.com/realms/partner',
  client_id: 'partner-backend',
  enabled: false,
  public_url: null,
  role_mapping: {},
  sort_order: 0,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createTestStore(): Store {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(api.middleware),
  });
}

function renderAuthenticationPage() {
  const store = createTestStore();
  return {
    store,
    ...render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <AuthenticationSettings />
          </App>
        </BrowserRouter>
      </Provider>
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AuthenticationSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: loading state
    (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });
    // Default mutations: idle
    (useCreateOidcProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateOidcProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteOidcProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  // =========================================================================
  // 1. Basic rendering & loading
  // =========================================================================

  describe('loading and error states', () => {
    it('shows Spin while data is loading', () => {
      const { container } = renderAuthenticationPage();
      // antd Spin renders .ant-spin-spinning — no role="progressbar"
      expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
    });

    it('shows an error message when loading fails', () => {
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('fail'),
      });
      renderAuthenticationPage();
      expect(screen.getByText(/Failed to load authentication configuration/i)).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 2. Provider cards
  // =========================================================================

  describe('provider cards', () => {
    it('shows empty state when no providers are configured', () => {
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();
      expect(screen.getByText(/No OIDC providers configured/i)).toBeInTheDocument();
    });

    it('renders one card per provider with name, issuer and enabled badge', () => {
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [mockProviderA, mockProviderB],
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();

      expect(screen.getByText('Corporate Keycloak')).toBeInTheDocument();
      expect(screen.getByText('Partner Keycloak')).toBeInTheDocument();
      expect(screen.getByText('https://keycloak.example.com/realms/myrealm')).toBeInTheDocument();
      expect(screen.getByText('https://partner.example.com/realms/partner')).toBeInTheDocument();
      // Enabled badges: two Tags with Enabled/Disabled
      const badges = screen.getAllByText(/^(Enabled|Disabled)$/);
      expect(badges).toHaveLength(2);
    });

    it('renders cards in sort_order order', () => {
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        // B has sort_order 0 — must appear before A
        data: [mockProviderA, mockProviderB],
        isLoading: false,
        isError: false,
        error: null,
      });
      const { container } = renderAuthenticationPage();

      const titles = Array.from(container.querySelectorAll('.ant-card-head-title')).map(
        (el) => el.textContent ?? ''
      );
      expect(titles[0]).toContain('Partner Keycloak');
      expect(titles[1]).toContain('Corporate Keycloak');
    });

    it('shows Add Provider button', () => {
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [mockProviderA],
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();
      expect(screen.getByRole('button', { name: /add provider/i })).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 3. Edit modal
  // =========================================================================

  describe('edit modal', () => {
    it('opens edit modal with provider data when Edit is clicked', async () => {
      const user = userEvent.setup();
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [mockProviderA],
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();

      await user.click(screen.getByRole('button', { name: /edit provider corporate keycloak/i }));

      const dialog = await screen.findByRole('dialog');
      expect(dialog).toBeInTheDocument();
      expect(await screen.findByDisplayValue('Corporate Keycloak')).toBeInTheDocument();
      expect(
        await screen.findByDisplayValue('https://keycloak.example.com/realms/myrealm')
      ).toBeInTheDocument();
      // Secret is masked → empty field with placeholder
      expect(screen.getByPlaceholderText(/Enter new secret to change/i)).toBeInTheDocument();
    });

    it('submits updated fields to updateOidcProvider with provider id', async () => {
      const user = userEvent.setup();
      const updateMock = vi.fn().mockReturnValue({
        unwrap: () => Promise.resolve(mockProviderA),
      });
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [mockProviderA],
        isLoading: false,
        isError: false,
        error: null,
      });
      (useUpdateOidcProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        updateMock,
        { isLoading: false },
      ]);
      renderAuthenticationPage();

      await user.click(screen.getByRole('button', { name: /edit provider corporate keycloak/i }));
      const nameInput = await screen.findByLabelText('Provider display name');
      await user.clear(nameInput);
      await user.type(nameInput, 'Renamed Keycloak');
      await user.click(screen.getByRole('button', { name: 'Save' }));

      await waitFor(() => {
        expect(updateMock).toHaveBeenCalled();
      });
      const call = updateMock.mock.calls[0][0] as { id: number; data: { name?: string } };
      expect(call.id).toBe(1);
      expect(call.data.name).toBe('Renamed Keycloak');
    });

    it('surfaces backend 422 validation detail as an error message', async () => {
      const user = userEvent.setup();
      const updateMock = vi.fn().mockReturnValue({
        unwrap: () =>
          Promise.reject({
            data: { detail: [{ msg: 'issuer_url must contain /realms/<realm> segment' }] },
          }),
      });
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [mockProviderA],
        isLoading: false,
        isError: false,
        error: null,
      });
      (useUpdateOidcProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        updateMock,
        { isLoading: false },
      ]);
      renderAuthenticationPage();

      await user.click(screen.getByRole('button', { name: /edit provider corporate keycloak/i }));
      const issuerInput = await screen.findByDisplayValue(
        'https://keycloak.example.com/realms/myrealm'
      );
      await user.clear(issuerInput);
      await user.type(issuerInput, 'https://keycloak.example.com');
      await user.click(screen.getByRole('button', { name: 'Save' }));

      await waitFor(() => {
        expect(screen.getByText(/issuer_url must contain/i)).toBeInTheDocument();
      });
    });
  });

  // =========================================================================
  // 4. Create
  // =========================================================================

  describe('create', () => {
    it('opens empty modal and submits createOidcProvider', async () => {
      const user = userEvent.setup();
      const createMock = vi.fn().mockReturnValue({
        unwrap: () => Promise.resolve(mockProviderA),
      });
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [mockProviderA],
        isLoading: false,
        isError: false,
        error: null,
      });
      (useCreateOidcProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        createMock,
        { isLoading: false },
      ]);
      renderAuthenticationPage();

      await user.click(screen.getByRole('button', { name: /add provider/i }));
      await screen.findByRole('dialog');

      await user.type(await screen.findByLabelText('Provider display name'), 'New Provider');
      await user.type(
        screen.getByPlaceholderText('https://kc.example.com/realms/myrealm'),
        'https://kc.new/realms/new'
      );
      await user.type(screen.getByPlaceholderText('bigbug-backend'), 'new-backend');
      await user.click(screen.getByRole('button', { name: 'Save' }));

      await waitFor(() => {
        expect(createMock).toHaveBeenCalled();
      });
      const payload = createMock.mock.calls[0][0] as {
        name: string;
        issuer_url: string;
        client_id: string;
      };
      expect(payload.name).toBe('New Provider');
      expect(payload.issuer_url).toBe('https://kc.new/realms/new');
      expect(payload.client_id).toBe('new-backend');
    });
  });

  // =========================================================================
  // 5. Delete & toggle
  // =========================================================================

  describe('delete and toggle', () => {
    it('deletes a provider after confirm', async () => {
      const user = userEvent.setup();
      const deleteMock = vi.fn().mockReturnValue({ unwrap: () => Promise.resolve(undefined) });
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [mockProviderA],
        isLoading: false,
        isError: false,
        error: null,
      });
      (useDeleteOidcProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        deleteMock,
        { isLoading: false },
      ]);
      renderAuthenticationPage();

      await user.click(screen.getByRole('button', { name: /delete provider corporate keycloak/i }));
      await user.click(await screen.findByRole('button', { name: 'Delete' }));

      await waitFor(() => {
        expect(deleteMock).toHaveBeenCalledWith(1);
      });
    });

    it('toggles provider enabled state via updateOidcProvider', async () => {
      const user = userEvent.setup();
      const updateMock = vi.fn().mockReturnValue({ unwrap: () => Promise.resolve(mockProviderB) });
      (useGetOidcProvidersQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: [mockProviderB],
        isLoading: false,
        isError: false,
        error: null,
      });
      (useUpdateOidcProviderMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        updateMock,
        { isLoading: false },
      ]);
      renderAuthenticationPage();

      await user.click(screen.getByLabelText('Toggle provider Partner Keycloak'));

      await waitFor(() => {
        expect(updateMock).toHaveBeenCalledWith({ id: 2, data: { enabled: true } });
      });
    });
  });
});
