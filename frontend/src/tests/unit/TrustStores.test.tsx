/**
 * @file TrustStores.test.tsx
 * @description Unit tests for the Admin TrustStores page — list rendering with
 *              mocked RTK Query hooks (no store wiring).
 * @dependencies Vitest, @testing-library/react
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
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

import {
  useGetTrustStoresQuery,
  useGetTrustStoreUsageQuery,
  useAddTrustStoreCertificatesMutation,
  useDeleteTrustStoreCertificateMutation,
  useDeleteTrustStoreMutation,
  useCreateTrustStoreMutation,
  useUpdateTrustStoreMutation,
} from '../../store/api';
import AdminTrustStores from '../../pages/Admin/TrustStores';
import { usePermissions } from '../../hooks/usePermissions';
import type { TrustStore } from '../../types';

function mockStore(overrides: Partial<TrustStore> = {}): TrustStore {
  return {
    id: 1,
    name: 'corporate-ca',
    description: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    certificates: [
      {
        id: 10,
        name: 'root',
        pem: '-----BEGIN CERTIFICATE-----',
        fingerprint: 'a'.repeat(64),
        created_at: '2026-01-01T00:00:00Z',
      },
    ],
    ...overrides,
  };
}

describe('AdminTrustStores (unit)', () => {
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
    (useCreateTrustStoreMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateTrustStoreMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useAddTrustStoreCertificatesMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteTrustStoreCertificateMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteTrustStoreMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  it('renders trust store names and certificate count', () => {
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [mockStore(), mockStore({ id: 2, name: 'public-ca', certificates: [] })],
      isLoading: false,
      isError: false,
    });
    render(
      <App>
        <AdminTrustStores />
      </App>
    );
    expect(screen.getByText('corporate-ca')).toBeInTheDocument();
    expect(screen.getByText('public-ca')).toBeInTheDocument();
    expect(screen.getByText('1 CA')).toBeInTheDocument();
    expect(screen.getByText('0 CA')).toBeInTheDocument();
  });

  it('shows spinner while loading', () => {
    (useGetTrustStoresQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: true,
      isError: false,
    });
    render(
      <App>
        <AdminTrustStores />
      </App>
    );
    expect(document.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });
});
