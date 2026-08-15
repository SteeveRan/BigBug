/**
 * @file ProviderDetail.test.tsx
 * @description Integration tests for the provider detail page
 *              (`/settings/providers/:providerId`). Verifies the Breadcrumb
 *              (Providers / {domain} / {name}) and rendered metadata.
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, react-router
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import type { Store } from '@reduxjs/toolkit';
import { App } from 'antd';

// Mock react-router
const mockNavigate = vi.fn();
vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ providerId: '1' }),
  useLocation: () => ({
    pathname: '/settings/providers/1',
    search: '',
    hash: '',
    state: null,
  }),
  Navigate: ({ to }: { to: string }) => <div data-testid="navigate" data-to={to} />,
  Outlet: () => <div data-testid="outlet" />,
  Link: ({ children, ...props }: Record<string, unknown>) => (
    <a {...props}>{children as React.ReactNode}</a>
  ),
}));

// Mock RTK Query hooks
vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetProviderQuery: vi.fn(),
  };
});

import { api } from '../../store/api';
import { useGetProviderQuery } from '../../store/api';
import { ProviderDetailPage } from '../../pages/Settings/Providers/ProviderDetail';
import type { ResourceProvider } from '../../types';

function createTestStore(): Store {
  return configureStore({
    reducer: { [api.reducerPath]: api.reducer },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function mockProvider(overrides: Partial<ResourceProvider> = {}): ResourceProvider {
  return {
    id: 1,
    domain: 'docker',
    subtype: 'docker_hub',
    category: 'private',
    direction: 'external',
    name: 'docker_hub_main',
    label: 'Docker Hub',
    description: 'Primary Docker Hub registry',
    base_url: 'https://registry-1.docker.io',
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
    updated_at: '2026-01-02T00:00:00Z',
    has_credential: false,
    ...overrides,
  };
}

describe('ProviderDetailPage', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    store = createTestStore();
    vi.clearAllMocks();
  });

  function renderPage() {
    return render(
      <Provider store={store}>
        <App>
          <ProviderDetailPage />
        </App>
      </Provider>
    );
  }

  it('renders Breadcrumb with Providers, domain and provider name', () => {
    (useGetProviderQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockProvider(),
      isLoading: false,
      isError: false,
    });

    renderPage();

    expect(screen.getByText('Providers')).toBeInTheDocument();
    // "Docker" appears both in the Breadcrumb (domain) and Descriptions (Domain tag).
    expect(screen.getAllByText('Docker').length).toBeGreaterThanOrEqual(1);
    // The name is shown in the breadcrumb AND in the Descriptions (Name).
    expect(screen.getAllByText('docker_hub_main').length).toBeGreaterThanOrEqual(1);
  });

  it('renders provider metadata via Descriptions', () => {
    (useGetProviderQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockProvider(),
      isLoading: false,
      isError: false,
    });

    renderPage();

    expect(screen.getByText('Provider Info')).toBeInTheDocument();
    // Label appears both as the page heading and in the Descriptions (Label).
    expect(screen.getAllByText('Docker Hub').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Primary Docker Hub registry')).toBeInTheDocument();
    expect(screen.getByText('https://registry-1.docker.io')).toBeInTheDocument();
    expect(screen.getByText('docker_hub')).toBeInTheDocument();
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  it('shows loading spinner while fetching', () => {
    (useGetProviderQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    const { container } = renderPage();
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  it('shows error alert when provider fails to load', () => {
    (useGetProviderQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    renderPage();
    expect(screen.getByText('Failed to load provider')).toBeInTheDocument();
  });

  it('navigates back to providers list when clicking Providers breadcrumb', async () => {
    (useGetProviderQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockProvider(),
      isLoading: false,
      isError: false,
    });

    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByText('Providers'));
    expect(mockNavigate).toHaveBeenCalledWith('/settings/providers');
  });
});
