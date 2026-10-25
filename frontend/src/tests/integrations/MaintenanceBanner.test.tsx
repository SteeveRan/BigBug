/**
 * @file MaintenanceBanner.test.tsx
 * @description Integration tests for the global MaintenanceBanner:
 *              shows when maintenance_mode=true, hidden when false,
 *              renders nothing while the first fetch is in flight (no flash).
 * @dependencies Vitest, @testing-library/react
 * @relatedFiles ../../components/MaintenanceBanner/index.tsx, ../../hooks/useMaintenanceMode.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetMaintenanceStatusQuery: vi.fn(),
  };
});

import { api } from '../../store/api';
import { useGetMaintenanceStatusQuery } from '../../store/api';
import { MaintenanceBanner } from '../../components/MaintenanceBanner';
import authReducer from '../../store/authSlice';

const mockedQuery = useGetMaintenanceStatusQuery as ReturnType<typeof vi.fn>;

function renderBanner() {
  const store = configureStore({
    reducer: { auth: authReducer, [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
  return render(
    <Provider store={store}>
      <BrowserRouter>
        <MaintenanceBanner />
      </BrowserRouter>
    </Provider>
  );
}

describe('MaintenanceBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the banner when maintenance_mode is true', () => {
    mockedQuery.mockReturnValue({ data: { maintenance_mode: true } });
    renderBanner();
    expect(
      screen.getByText('Идут технические работы — фоновая синхронизация приостановлена')
    ).toBeInTheDocument();
  });

  it('renders nothing when maintenance_mode is false', () => {
    mockedQuery.mockReturnValue({ data: { maintenance_mode: false } });
    const { container } = renderBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing while the first fetch is in flight (no flash)', () => {
    mockedQuery.mockReturnValue({ data: undefined });
    const { container } = renderBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it('polls every 30 seconds', () => {
    mockedQuery.mockReturnValue({ data: { maintenance_mode: false } });
    renderBanner();
    expect(mockedQuery).toHaveBeenCalledWith(undefined, { pollingInterval: 30_000 });
  });
});
