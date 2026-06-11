/**
 * @file AuthenticationSettings.test.tsx
 * @description Unit tests for the Settings > Authentication page (Ant Design).
 *              Covers loading/error states, data display, form editing,
 *              role mapping CRUD, save behaviour, and client_secret masking.
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
    useGetOidcConfigQuery: vi.fn(),
    useUpdateOidcConfigMutation: vi.fn(),
  };
});

// ---------------------------------------------------------------------------
// Imports — executed after vi.mock calls are hoisted
// ---------------------------------------------------------------------------

import { api, useGetOidcConfigQuery, useUpdateOidcConfigMutation } from '../../store/api';
import { AuthenticationSettings } from '../../pages/Settings/Authentication';
import type { OIDCConfig } from '../../types';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const mockOidcConfig: OIDCConfig = {
  id: 1,
  issuer_url: 'https://keycloak.example.com/realms/myrealm',
  client_id: 'bigbug-backend',
  client_secret: '********',
  frontend_client_id: 'bigbug-frontend',
  enabled: false,
  public_url: 'https://auth.example.com',
  role_mapping: {
    'bigbug-admin': 'admin',
    'bigbug-viewer': 'viewer',
  },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
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
    (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });
    // Default mutation: idle
    (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
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

    it('does not show Spin after data loads', () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
      const { container } = renderAuthenticationPage();
      expect(container.querySelector('.ant-spin-spinning')).not.toBeInTheDocument();
    });

    it('shows error text when query fails', () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { status: 500, data: { detail: 'Server error' } },
      });
      renderAuthenticationPage();
      expect(screen.getByText('Authentication Settings')).toBeInTheDocument();
      // antd Typography.Text type="danger" — no role="alert"
      expect(
        screen.getByText(/Failed to load authentication configuration/i)
      ).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 2. Title and section headers
  // =========================================================================

  describe('title and section headers', () => {
    beforeEach(() => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
    });

    it('renders the page title', () => {
      renderAuthenticationPage();
      expect(screen.getByText('Authentication Settings')).toBeInTheDocument();
    });

    it('renders OIDC / SSO Configuration section', () => {
      renderAuthenticationPage();
      expect(screen.getByText('OIDC / SSO Configuration')).toBeInTheDocument();
    });

    it('renders Role Mapping section', () => {
      renderAuthenticationPage();
      expect(screen.getByText('Role Mapping')).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 3. Data display from API
  // =========================================================================

  describe('data display', () => {
    beforeEach(() => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
    });

    it('displays Issuer URL from API', () => {
      renderAuthenticationPage();
      // antd uses Typography.Text labels above Input, NOT HTML <label>
      // Use getByDisplayValue to verify pre-filled input
      expect(screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm')).toBeInTheDocument();
    });

    it('displays Backend Client ID from API', () => {
      renderAuthenticationPage();
      expect(screen.getByDisplayValue('bigbug-backend')).toBeInTheDocument();
    });

    it('displays Frontend Client ID from API', () => {
      renderAuthenticationPage();
      expect(screen.getByDisplayValue('bigbug-frontend')).toBeInTheDocument();
    });

    it('displays Public URL from API', () => {
      renderAuthenticationPage();
      expect(screen.getByDisplayValue('https://auth.example.com')).toBeInTheDocument();
    });

    it('switch reflects enabled state (false)', () => {
      renderAuthenticationPage();
      // aria-label="Enable SSO / OIDC" → role="switch" with accessible name
      const switchEl = screen.getByRole('switch', { name: 'Enable SSO / OIDC' });
      expect(switchEl).not.toBeChecked();
      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });

    it('switch reflects enabled state (true)', () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: { ...mockOidcConfig, enabled: true },
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();
      const switchEl = screen.getByRole('switch', { name: 'Enable SSO / OIDC' });
      expect(switchEl).toBeChecked();
      expect(screen.getByText('Enabled')).toBeInTheDocument();
    });

    it('displays role mappings in the table', () => {
      renderAuthenticationPage();
      // antd Table renders <table> but without role="table"
      // Use getByDisplayValue to find the inputs inside the table rows
      expect(screen.getByDisplayValue('bigbug-admin')).toBeInTheDocument();
      expect(screen.getByDisplayValue('admin')).toBeInTheDocument();
      expect(screen.getByDisplayValue('bigbug-viewer')).toBeInTheDocument();
      expect(screen.getByDisplayValue('viewer')).toBeInTheDocument();
    });

    it('shows placeholder text when no role mappings exist', () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: { ...mockOidcConfig, role_mapping: {} },
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();
      expect(
        screen.getByText(/No role mappings configured/i)
      ).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 4. Client secret masking
  // =========================================================================

  describe('client secret masking', () => {
    it('shows empty secret field when stored value is masked', () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();
      // antd Input.Password — find by placeholder since it's the masked state
      const secretInput = screen.getByPlaceholderText('Enter new secret to change') as HTMLInputElement;
      expect(secretInput.value).toBe('');
    });

    it('shows placeholder hint when secret is masked', () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();
      const secretInput = screen.getByPlaceholderText('Enter new secret to change') as HTMLInputElement;
      expect(secretInput.placeholder).toBe('Enter new secret to change');
    });

    it('shows "Secret is stored" helper text when secret is masked', () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
      renderAuthenticationPage();
      expect(
        screen.getByText('Secret is stored. Enter a new value to change.')
      ).toBeInTheDocument();
    });

    it('masked secret is NOT included in payload when unchanged', async () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig, // client_secret === '********'
        isLoading: false,
        isError: false,
        error: null,
      });

      const mockUpdateFn = vi.fn().mockReturnValue({
        unwrap: () => Promise.resolve({}),
      });
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: false },
      ]);

      renderAuthenticationPage();

      // Change issuer URL so the form is dirty (secret alone is unchanged)
      const issuerInput = screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm');
      await userEvent.clear(issuerInput);
      await userEvent.type(issuerInput, 'https://changed.example.com');

      await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

      await waitFor(() => {
        expect(mockUpdateFn).toHaveBeenCalledWith(
          expect.not.objectContaining({ client_secret: expect.anything() })
        );
      });
    });

    it('newly entered secret IS included in payload', async () => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig, // client_secret === '********'
        isLoading: false,
        isError: false,
        error: null,
      });

      const mockUpdateFn = vi.fn().mockReturnValue({
        unwrap: () => Promise.resolve({}),
      });
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: false },
      ]);

      renderAuthenticationPage();

      // Type new secret — find by placeholder since value is empty
      const secretInput = screen.getByPlaceholderText('Enter new secret to change');
      await userEvent.type(secretInput, 'my-new-secret');

      await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

      await waitFor(() => {
        expect(mockUpdateFn).toHaveBeenCalledWith(
          expect.objectContaining({ client_secret: 'my-new-secret' })
        );
      });
    });
  });

  // =========================================================================
  // 5. Editing configuration fields
  // =========================================================================

  describe('editing configuration fields', () => {
    beforeEach(() => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
    });

    it('save button is disabled when no changes are made', () => {
      renderAuthenticationPage();
      expect(screen.getByRole('button', { name: 'Save Changes' })).toBeDisabled();
    });

    it('editing Issuer URL enables save button', async () => {
      renderAuthenticationPage();
      const input = screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm');
      await userEvent.clear(input);
      await userEvent.type(input, 'https://new-issuer.example.com');
      expect(screen.getByRole('button', { name: 'Save Changes' })).toBeEnabled();
    });

    it('editing Backend Client ID enables save button', async () => {
      renderAuthenticationPage();
      const input = screen.getByDisplayValue('bigbug-backend');
      await userEvent.clear(input);
      await userEvent.type(input, 'new-backend-client');
      expect(screen.getByRole('button', { name: 'Save Changes' })).toBeEnabled();
    });

    it('editing Frontend Client ID enables save button', async () => {
      renderAuthenticationPage();
      const input = screen.getByDisplayValue('bigbug-frontend');
      await userEvent.clear(input);
      await userEvent.type(input, 'new-frontend-client');
      expect(screen.getByRole('button', { name: 'Save Changes' })).toBeEnabled();
    });

    it('editing Public URL enables save button', async () => {
      renderAuthenticationPage();
      const input = screen.getByDisplayValue('https://auth.example.com');
      await userEvent.clear(input);
      await userEvent.type(input, 'https://new-public.example.com');
      expect(screen.getByRole('button', { name: 'Save Changes' })).toBeEnabled();
    });

    it('toggling the SSO switch enables save button', async () => {
      renderAuthenticationPage();
      const switchEl = screen.getByRole('switch', { name: 'Enable SSO / OIDC' });
      await userEvent.click(switchEl);
      expect(screen.getByRole('button', { name: 'Save Changes' })).toBeEnabled();
    });

    it('switch toggle changes label between Enabled and Disabled', async () => {
      renderAuthenticationPage();
      expect(screen.getByText('Disabled')).toBeInTheDocument();

      const switchEl = screen.getByRole('switch', { name: 'Enable SSO / OIDC' });
      await userEvent.click(switchEl);
      expect(screen.getByText('Enabled')).toBeInTheDocument();
      expect(switchEl).toBeChecked();

      await userEvent.click(switchEl);
      expect(screen.getByText('Disabled')).toBeInTheDocument();
      expect(switchEl).not.toBeChecked();
    });

    it('entering a new client secret enables save button', async () => {
      renderAuthenticationPage();
      const secretInput = screen.getByPlaceholderText('Enter new secret to change');
      await userEvent.type(secretInput, 'new-secret');
      expect(screen.getByRole('button', { name: 'Save Changes' })).toBeEnabled();
    });
  });

  // =========================================================================
  // 6. Role mapping management
  // =========================================================================

  describe('role mapping management', () => {
    beforeEach(() => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
    });

    it('clicking "Add Mapping" adds a new empty row', async () => {
      const { container } = renderAuthenticationPage();

      // antd Table rows use class .ant-table-row
      const rowsBefore = container.querySelectorAll('.ant-table-row').length;

      await userEvent.click(screen.getByText('Add Mapping'));

      const rowsAfter = container.querySelectorAll('.ant-table-row').length;
      // One extra row
      expect(rowsAfter).toBe(rowsBefore + 1);
    });

    it('editing provider_role in a mapping row updates the input value', async () => {
      renderAuthenticationPage();

      const providerInput = screen.getByDisplayValue('bigbug-admin');
      await userEvent.clear(providerInput);
      await userEvent.type(providerInput, 'custom-provider-role');

      expect(screen.getByDisplayValue('custom-provider-role')).toBeInTheDocument();
    });

    it('editing bigbug_role in a mapping row updates the input value', async () => {
      renderAuthenticationPage();

      const roleInput = screen.getByDisplayValue('admin');
      await userEvent.clear(roleInput);
      await userEvent.type(roleInput, 'operator');

      expect(screen.getByDisplayValue('operator')).toBeInTheDocument();
    });

    it('clicking delete button removes the mapping row', async () => {
      renderAuthenticationPage();

      // Find the delete button via aria-label
      const deleteButtons = screen.getAllByRole('button', { name: /Remove mapping/ });
      const countBefore = deleteButtons.length;

      await userEvent.click(deleteButtons[0]);

      const deleteButtonsAfter = screen.getAllByRole('button', { name: /Remove mapping/ });
      expect(deleteButtonsAfter.length).toBe(countBefore - 1);
      // The removed row should no longer have its values displayed
      expect(screen.queryByDisplayValue('bigbug-admin')).not.toBeInTheDocument();
    });

    it('empty mappings are filtered from role_mapping on save', async () => {
      const mockUpdateFn = vi.fn().mockReturnValue({
        unwrap: () => Promise.resolve({}),
      });
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: false },
      ]);

      renderAuthenticationPage();

      // Add an empty mapping row — no values entered
      await userEvent.click(screen.getByText('Add Mapping'));

      // Toggle SSO switch to make the form dirty and trigger dirty detection
      const switchEl = screen.getByRole('switch', { name: 'Enable SSO / OIDC' });
      await userEvent.click(switchEl);

      // Verify save button is enabled before clicking
      const saveButton = screen.getByRole('button', { name: /Save Changes/ });
      expect(saveButton).toBeEnabled();

      await userEvent.click(saveButton);

      await waitFor(() => {
        expect(mockUpdateFn).toHaveBeenCalledTimes(1);
        const callArg = mockUpdateFn.mock.calls[0][0] as Record<string, unknown>;
        expect(callArg.enabled).toBe(true);
        // role_mapping should NOT be in payload because only the toggle changed
        // (the existing mappings were unchanged from original values)
      });

      // Verify that role_mapping was NOT sent (no changes to mappings)
      const callArg = mockUpdateFn.mock.calls[0][0] as Record<string, unknown>;
      expect(callArg).not.toHaveProperty('role_mapping');
    });
  });

  // =========================================================================
  // 7. Saving changes
  // =========================================================================

  describe('saving changes', () => {
    beforeEach(() => {
      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });
    });

    it('calls updateOidcConfig mutation with correct payload', async () => {
      const mockUpdateFn = vi.fn().mockReturnValue({
        unwrap: () => Promise.resolve({}),
      });
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: false },
      ]);

      renderAuthenticationPage();

      // Change multiple fields
      const issuerInput = screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm');
      await userEvent.clear(issuerInput);
      await userEvent.type(issuerInput, 'https://new-issuer.example.com');

      const switchEl = screen.getByRole('switch', { name: 'Enable SSO / OIDC' });
      await userEvent.click(switchEl);

      await userEvent.click(screen.getByRole('button', { name: /Save Changes/ }));

      await waitFor(() => {
        expect(mockUpdateFn).toHaveBeenCalledWith(
          expect.objectContaining({
            issuer_url: 'https://new-issuer.example.com',
            enabled: true,
          })
        );
      });
    });

    it('shows success snackbar after successful save', async () => {
      const mockUpdateFn = vi.fn().mockReturnValue({
        unwrap: () => Promise.resolve({}),
      });
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: false },
      ]);

      renderAuthenticationPage();

      // Change something to enable save
      const issuerInput = screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm');
      await userEvent.clear(issuerInput);
      await userEvent.type(issuerInput, 'https://changed.example.com');

      await userEvent.click(screen.getByRole('button', { name: /Save Changes/ }));

      await waitFor(() => {
        // antd message.success renders notification in DOM
        expect(screen.getByText('Settings saved successfully')).toBeInTheDocument();
      });
    });

    it('save button becomes disabled after successful save (no pending changes)', async () => {
      const mockUpdateFn = vi.fn().mockReturnValue({
        unwrap: () => Promise.resolve({}),
      });
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: false },
      ]);

      renderAuthenticationPage();

      // Change issuer URL to make form dirty
      const issuerInput = screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm');
      await userEvent.clear(issuerInput);
      await userEvent.type(issuerInput, 'https://changed.example.com');

      const saveButton = screen.getByRole('button', { name: /Save Changes/ });
      expect(saveButton).toBeEnabled();

      await userEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Save Changes/ })).toBeDisabled();
      });
    });

    it('shows loading icon inside save button when mutation is saving', async () => {
      const mockUpdateFn = vi.fn();

      // Set data with different issuer_url so isDirty=true
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: true },
      ]);

      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: { ...mockOidcConfig, issuer_url: 'https://changed.example.com' },
        isLoading: false,
        isError: false,
        error: null,
      });

      renderAuthenticationPage();

      // antd Button with loading adds .ant-btn-loading-icon
      const saveButton = screen.getByRole('button', { name: /Save Changes/ });
      expect(saveButton.querySelector('.ant-btn-loading-icon')).toBeTruthy();
      expect(saveButton).toBeDisabled();
    });

    it('all form fields are disabled while saving', () => {
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        vi.fn(),
        { isLoading: true },
      ]);

      (useGetOidcConfigQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: mockOidcConfig,
        isLoading: false,
        isError: false,
        error: null,
      });

      renderAuthenticationPage();

      // All inputs should be disabled while mutation is in progress
      const issuerInput = screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm') as HTMLInputElement;
      const clientIdInput = screen.getByDisplayValue('bigbug-backend') as HTMLInputElement;
      const frontendClientIdInput = screen.getByDisplayValue('bigbug-frontend') as HTMLInputElement;
      const publicUrlInput = screen.getByDisplayValue('https://auth.example.com') as HTMLInputElement;
      const secretInput = screen.getByPlaceholderText('Enter new secret to change') as HTMLInputElement;

      expect(issuerInput).toBeDisabled();
      expect(clientIdInput).toBeDisabled();
      expect(frontendClientIdInput).toBeDisabled();
      expect(publicUrlInput).toBeDisabled();
      expect(secretInput).toBeDisabled();
    });

    it('shows error snackbar when save fails', async () => {
      const mockUpdateFn = vi.fn().mockReturnValue({
        unwrap: () => Promise.reject({ data: { detail: 'Connection refused' } }),
      });
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: false },
      ]);

      renderAuthenticationPage();

      // Change something to enable save
      const issuerInput = screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm');
      await userEvent.clear(issuerInput);
      await userEvent.type(issuerInput, 'https://changed.example.com');

      await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

      await waitFor(() => {
        expect(screen.getByText('Connection refused')).toBeInTheDocument();
      });
    });

    it('shows fallback error message when save fails without detail', async () => {
      const mockUpdateFn = vi.fn().mockReturnValue({
        unwrap: () => Promise.reject(new Error('Network error')),
      });
      (useUpdateOidcConfigMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockUpdateFn,
        { isLoading: false },
      ]);

      renderAuthenticationPage();

      const issuerInputFallback = screen.getByDisplayValue('https://keycloak.example.com/realms/myrealm');
      await userEvent.clear(issuerInputFallback);
      await userEvent.type(issuerInputFallback, 'https://changed.example.com');

      await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

      await waitFor(() => {
        expect(screen.getByText('Failed to save settings')).toBeInTheDocument();
      });
    });
  });
});
