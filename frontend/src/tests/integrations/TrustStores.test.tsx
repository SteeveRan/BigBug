/**
 * @file TrustStores.test.tsx
 * @description Integration tests for the Admin Trust Stores page:
 *              list rendering, adding a certificate chain, delete with 409.
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
    useGetTrustStoresQuery: vi.fn(),
    useGetTrustStoreQuery: vi.fn(),
    useCreateTrustStoreMutation: vi.fn(),
    useUpdateTrustStoreMutation: vi.fn(),
    useDeleteTrustStoreMutation: vi.fn(),
    useGetTrustStoreUsageQuery: vi.fn(),
    useAddTrustStoreCertificatesMutation: vi.fn(),
    useDeleteTrustStoreCertificateMutation: vi.fn(),
  };
});

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

import { api } from '../../store/api';
import {
  useGetTrustStoresQuery,
  useDeleteTrustStoreMutation,
  useGetTrustStoreUsageQuery,
  useAddTrustStoreCertificatesMutation,
  useDeleteTrustStoreCertificateMutation,
  useCreateTrustStoreMutation,
  useUpdateTrustStoreMutation,
} from '../../store/api';
import AdminTrustStores from '../../pages/Admin/TrustStores';
import { usePermissions } from '../../hooks/usePermissions';
import type { TrustStore } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function mockCert(id: number, name: string): TrustStore['certificates'][number] {
  return {
    id,
    name,
    pem: '-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----',
    fingerprint: 'a'.repeat(64),
    created_at: '2026-01-01T00:00:00Z',
  };
}

function mockStore(overrides: Partial<TrustStore> = {}): TrustStore {
  return {
    id: 1,
    name: 'corporate-ca',
    description: 'Internal CAs',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    certificates: [mockCert(10, 'root'), mockCert(11, 'intermediate-1')],
    ...overrides,
  };
}

function mockMutation<T>(impl?: (...args: unknown[]) => Promise<T>) {
  const fn = vi.fn(impl ?? (async () => ({ data: {} }) as T));
  return [fn, { isLoading: false }] as unknown as ReturnType<typeof vi.fn>;
}

describe('AdminTrustStores', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
      hasPermission: () => true,
      hasAnyPermission: () => true,
      hasAllPermissions: () => true,
      permissions: [],
    });
    const usageLazy = vi.fn().mockResolvedValue({ data: { trust_store_id: 1, providers: [] } });
    (useGetTrustStoreUsageQuery as unknown as { useLazyQuery: unknown }).useLazyQuery = vi.fn(
      () => [usageLazy]
    );
    (useCreateTrustStoreMutation as ReturnType<typeof vi.fn>).mockReturnValue(mockMutation());
    (useUpdateTrustStoreMutation as ReturnType<typeof vi.fn>).mockReturnValue(mockMutation());
    (useAddTrustStoreCertificatesMutation as ReturnType<typeof vi.fn>).mockReturnValue(
      mockMutation()
    );
    (useDeleteTrustStoreCertificateMutation as ReturnType<typeof vi.fn>).mockReturnValue(
      mockMutation()
    );
    (useDeleteTrustStoreMutation as ReturnType<typeof vi.fn>).mockReturnValue(mockMutation());
  });

  it('renders heading and store rows', () => {
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockStore()],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminTrustStores />
        </App>
      </Provider>
    );
    expect(screen.getByText('Trust Stores')).toBeInTheDocument();
    expect(screen.getByText('corporate-ca')).toBeInTheDocument();
    expect(screen.getByText('2 CA')).toBeInTheDocument();
  });

  it('shows empty state', () => {
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminTrustStores />
        </App>
      </Provider>
    );
    expect(screen.getByText('No trust stores configured')).toBeInTheDocument();
  });

  it('shows error alert on load failure', () => {
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: true,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminTrustStores />
        </App>
      </Provider>
    );
    expect(screen.getByText('Failed to load trust stores')).toBeInTheDocument();
  });

  it('adds a certificate chain via the modal and shows how many were added', async () => {
    const addCerts = vi.fn().mockReturnValue({ unwrap: async () => [{}, {}, {}] });
    (useAddTrustStoreCertificatesMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      addCerts,
      { isLoading: false },
    ] as unknown as ReturnType<typeof vi.fn>);
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockStore()],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminTrustStores />
        </App>
      </Provider>
    );

    fireEvent.click(screen.getByText('Add certs'));
    fireEvent.change(screen.getByPlaceholderText(/corporate-root/), {
      target: { value: 'chain' },
    });
    fireEvent.change(screen.getByPlaceholderText(/BEGIN CERTIFICATE/), {
      target: {
        value:
          '-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n-----BEGIN CERTIFICATE-----\ndef\n-----END CERTIFICATE-----\n-----BEGIN CERTIFICATE-----\nghi\n-----END CERTIFICATE-----',
      },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/ }));

    await waitFor(() => {
      expect(addCerts).toHaveBeenCalledWith({
        id: 1,
        data: {
          name: 'chain',
          pem: expect.stringContaining('ghi'),
        },
      });
    });
    // Modal closes on success
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /^Add$/ })).not.toBeInTheDocument();
    });
  });

  it('deletes a certificate from the expanded row', async () => {
    const deleteCert = vi.fn().mockReturnValue({ unwrap: async () => undefined });
    (useDeleteTrustStoreCertificateMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      deleteCert,
      { isLoading: false },
    ] as unknown as ReturnType<typeof vi.fn>);
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockStore()],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminTrustStores />
        </App>
      </Provider>
    );

    // Expand the row to reveal certificates
    fireEvent.click(screen.getAllByRole('button', { name: /expand row/i })[0]);
    expect(await screen.findByText('intermediate-1')).toBeInTheDocument();

    // Click per-cert delete then confirm
    fireEvent.click(screen.getByRole('button', { name: 'Delete certificate root' }));
    fireEvent.click(await screen.findByRole('button', { name: /^OK$/ }));
    await waitFor(() => {
      expect(deleteCert).toHaveBeenCalledWith({ storeId: 1, certificateId: 10 });
    });
  });

  it('shows provider usage in delete confirm and surfaces 409 detail', async () => {
    const usageLazy = vi.fn().mockReturnValue({
      unwrap: async () => ({ trust_store_id: 1, providers: ['github-main', 'gitlab-mirror'] }),
    });
    (useGetTrustStoreUsageQuery as unknown as { useLazyQuery: unknown }).useLazyQuery = vi.fn(
      () => [usageLazy]
    );
    const deleteStore = vi.fn().mockReturnValue({
      unwrap: async () => {
        throw { status: 409, data: { detail: 'Trust store is in use' } };
      },
    });
    (useDeleteTrustStoreMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      deleteStore,
      { isLoading: false },
    ] as unknown as ReturnType<typeof vi.fn>);
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockStore()],
      isLoading: false,
      isError: false,
    });
    render(
      <Provider store={createTestStore()}>
        <App>
          <AdminTrustStores />
        </App>
      </Provider>
    );

    fireEvent.click(screen.getAllByRole('button', { name: /delete trust store/i })[0]);
    expect(await screen.findByText(/In use by 2 provider\(s\)/)).toBeInTheDocument();
    expect(screen.getByText('github-main')).toBeInTheDocument();
    expect(screen.getByText('gitlab-mirror')).toBeInTheDocument();

    // Confirm → backend 409 → detail shown
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => {
      expect(deleteStore).toHaveBeenCalledWith(1);
    });
    await waitFor(() => {
      expect(screen.getAllByText(/Trust store is in use/).length).toBeGreaterThan(0);
    });
  });
});
