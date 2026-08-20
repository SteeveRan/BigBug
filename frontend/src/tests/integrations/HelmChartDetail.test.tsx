import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { App } from 'antd';
import { HelmChartDetailPage } from '../../pages/HelmCharts/HelmChartDetail';
import { api } from '../../store/api';
import authReducer, { setPermissions } from '../../store/authSlice';
import { STATUS_FLAG } from '../../types';

// Mock react-router
const mockNavigate = vi.fn();
vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ id: '1' }),
  useLocation: () => ({ pathname: '/mirroring/helm-charts/1', search: '', hash: '', state: null }),
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
    useGetHelmChartQuery: vi.fn(),
    useGetHelmChartVersionsQuery: vi.fn(),
    useGetHelmChartLogsQuery: vi.fn(),
    useIndexHelmChartMutation: vi.fn(),
    useMirrorHelmChartMutation: vi.fn(),
    useUpdateHelmChartMutation: vi.fn(),
  };
});

import {
  useGetHelmChartQuery,
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
  useIndexHelmChartMutation,
  useMirrorHelmChartMutation,
  useUpdateHelmChartMutation,
} from '../../store/api';

const mockIndexFn = vi.fn();
const mockMirrorFn = vi.fn();
const mockUpdateFn = vi.fn();

function createTestStore() {
  const store = configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
  store.dispatch(setPermissions(['helm:sync', 'helm:write']));
  return store;
}

const mockChart = {
  id: 1,
  name: 'stable',
  repo_url: 'https://charts.helm.sh/stable',
  description: 'Official Helm stable charts',
  provider_id: null,
  target_repo_url: 'oci://harbor.local/bigbug',
  last_synced_at: '2026-03-01T08:00:00Z',
  status_flag: STATUS_FLAG.OK,
  status_text: 'OK',
  gitlab_project_id: '12345',
  gitlab_project_url: 'https://gitlab.example.com/helm-mirror',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-03-01T08:00:00Z',
};

const mockVersions = [
  {
    id: 10,
    source_id: 1,
    chart_name: 'nginx-ingress',
    version: '4.0.1',
    app_version: '1.9.0',
    description: 'Ingress controller for Kubernetes using NGINX',
    digest: 'sha256:abc123',
    chart_url: 'https://charts.helm.sh/stable/nginx-ingress-4.0.1.tgz',
    is_synced: true,
    status_flag: STATUS_FLAG.OK,
    status_text: 'Synced',
    last_synced_at: '2026-03-01T08:00:00Z',
    created_at: '2026-03-01T08:00:00Z',
  },
];

const mockLogs = [
  {
    id: 100,
    source_id: 1,
    pipeline_id: '12345',
    pipeline_url: 'https://gitlab.example.com/pipelines/12345',
    chart_name: 'nginx-ingress',
    chart_version: '4.0.1',
    status_flag: STATUS_FLAG.OK,
    status_text: 'Completed',
    log_output: null,
    triggered_by: 'admin',
    started_at: '2026-03-01T08:00:00Z',
    finished_at: '2026-03-01T08:02:00Z',
    created_at: '2026-03-01T08:00:00Z',
  },
];

describe('HelmChartDetailPage', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    store = createTestStore();
    vi.clearAllMocks();
    mockIndexFn.mockReset();
    mockMirrorFn.mockReset();
    mockUpdateFn.mockReset();
    (useGetHelmChartQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockChart,
      isLoading: false,
      isError: false,
    });
    (useGetHelmChartVersionsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockVersions,
      isLoading: false,
      isError: false,
    });
    (useGetHelmChartLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockLogs,
      isLoading: false,
      isError: false,
    });
    (useIndexHelmChartMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockIndexFn,
      { isLoading: false },
    ]);
    (useMirrorHelmChartMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockMirrorFn,
      { isLoading: false },
    ]);
    (useUpdateHelmChartMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockUpdateFn,
      { isLoading: false },
    ]);
  });

  function renderPage() {
    return render(
      <Provider store={store}>
        <App>
          <HelmChartDetailPage />
        </App>
      </Provider>
    );
  }

  it('renders chart name as heading', () => {
    renderPage();
    expect(screen.getByText('stable')).toBeInTheDocument();
  });

  it('renders source info card with repo_url, status, last_synced', () => {
    renderPage();
    expect(screen.getByText('Source Info')).toBeInTheDocument();
    expect(screen.getByText('https://charts.helm.sh/stable')).toBeInTheDocument();
    // Only the Source Info card should contain the status text "OK"
    expect(screen.getByText('OK')).toBeInTheDocument();
    // last_synced formatted date — may appear in source info as well as
    // version/last-synced columns, so we check it exists at least once.
    const dateMatches = screen.getAllByText((content) => content.includes('3/1/2026'));
    expect(dateMatches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the versions table', () => {
    renderPage();
    expect(screen.getByText('Chart Versions (1)')).toBeInTheDocument();
    // "Chart" appears as column header AND hidden measurement div — use getAllByText
    expect(screen.getAllByText('Chart').length).toBeGreaterThanOrEqual(1);
    // "Version" also appears in hidden measurement div — use getAllByText
    expect(screen.getAllByText('Version').length).toBeGreaterThanOrEqual(1);
    // "App Version" also appears in hidden measurement div — use getAllByText
    expect(screen.getAllByText('App Version').length).toBeGreaterThanOrEqual(1);

    // Version data
    expect(screen.getByText('nginx-ingress')).toBeInTheDocument();
    expect(screen.getByText('4.0.1')).toBeInTheDocument();
    expect(screen.getByText('1.9.0')).toBeInTheDocument();
    expect(screen.getByText('✓ Synced')).toBeInTheDocument();
  });

  it('renders sync logs table', () => {
    renderPage();
    expect(screen.getByText('Sync History')).toBeInTheDocument();
    expect(screen.getByText('Date')).toBeInTheDocument();
    expect(screen.getByText('Triggered By')).toBeInTheDocument();
    expect(screen.getByText('Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();

    // Log data
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  it('calls indexChart when Re-index button is clicked', async () => {
    const user = userEvent.setup();
    renderPage();

    const reindexButton = screen.getByText('Re-index');
    await user.click(reindexButton);

    expect(mockIndexFn).toHaveBeenCalledWith(1);
  });

  it('shows loading spinner when isLoading', () => {
    (useGetHelmChartQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    const { container } = renderPage();
    // antd Spin renders with .ant-spin-spinning class
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  it('shows not found message when chart is null', () => {
    (useGetHelmChartQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
    });

    renderPage();
    expect(screen.getByText('Helm chart source not found')).toBeInTheDocument();
  });

  it('shows empty versions message', () => {
    (useGetHelmChartVersionsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    renderPage();
    expect(screen.getByText(/No versions indexed yet/)).toBeInTheDocument();
  });

  it('shows empty logs message', () => {
    (useGetHelmChartLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    renderPage();
    expect(screen.getByText('No sync history yet')).toBeInTheDocument();
  });

  it('shows the Mirror button when gitlab project is configured and permission granted', () => {
    renderPage();
    const mirrorButton = screen.getByRole('button', { name: /Mirror/ });
    expect(mirrorButton).toBeInTheDocument();
    expect(mirrorButton).not.toBeDisabled();
  });

  it('disables the Mirror button when no gitlab project is configured', () => {
    (useGetHelmChartQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { ...mockChart, gitlab_project_id: null },
      isLoading: false,
      isError: false,
    });
    renderPage();
    const mirrorButton = screen.getByRole('button', { name: /Mirror/ });
    expect(mirrorButton).toBeDisabled();
  });

  it('opens mirror dialog and calls the mutation with selected chart/version', async () => {
    const user = userEvent.setup();
    mockMirrorFn.mockReturnValue({
      unwrap: () => Promise.resolve({ status_flag: STATUS_FLAG.OK }),
    });
    renderPage();

    await user.click(screen.getByRole('button', { name: /Mirror/ }));

    const dialog = within(screen.getByRole('dialog'));
    expect(dialog.getByText('Mirror Chart')).toBeInTheDocument();

    await user.click(dialog.getByRole('button', { name: 'Mirror' }));

    expect(mockMirrorFn).toHaveBeenCalledWith({
      id: 1,
      chart_name: 'nginx-ingress',
      version: '4.0.1',
    });
  });
});
