import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { BrowserRouter } from 'react-router';
import { HelmChartsPage } from '../../pages/HelmCharts';
import { api } from '../../store/api';
import authReducer from '../../store/authSlice';
import { STATUS_FLAG } from '../../types';

// Mock RTK Query hooks
vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useListHelmChartsQuery: vi.fn(),
    useCreateHelmChartMutation: vi.fn(),
    useIndexHelmChartMutation: vi.fn(),
  };
});

import {
  useListHelmChartsQuery,
  useCreateHelmChartMutation,
  useIndexHelmChartMutation,
} from '../../store/api';

const mockCreateFn = vi.fn();
const mockIndexFn = vi.fn();

function createTestStore() {
  return configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

const mockCharts = [
  {
    id: 1,
    name: 'stable',
    repo_url: 'https://charts.helm.sh/stable',
    description: 'Official Helm stable charts',
    last_synced_at: '2026-01-15T10:00:00Z',
    status_flag: STATUS_FLAG.OK,
    status_text: 'Synced successfully',
    gitlab_project_id: null,
    gitlab_project_url: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
  },
];

describe('HelmChartsPage', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    store = createTestStore();
    vi.clearAllMocks();
    mockCreateFn.mockReset();
    mockIndexFn.mockReset();
    (useListHelmChartsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockCharts,
      isLoading: false,
      isError: false,
    });
    (useCreateHelmChartMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockCreateFn,
      { isLoading: false },
    ]);
    (useIndexHelmChartMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockIndexFn,
      { isLoading: false },
    ]);
  });

  function renderPage() {
    return render(
      <Provider store={store}>
        <BrowserRouter>
          <HelmChartsPage />
        </BrowserRouter>
      </Provider>
    );
  }

  it('renders the Helm Charts heading', () => {
    renderPage();
    expect(screen.getByText('Helm Charts')).toBeInTheDocument();
  });

  it('renders the table with Name, Repository URL, and Status columns', () => {
    renderPage();
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Repository URL')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();

    // Chart data
    expect(screen.getByText('stable')).toBeInTheDocument();
    expect(screen.getByText('https://charts.helm.sh/stable')).toBeInTheDocument();
    expect(screen.getByText('Synced successfully')).toBeInTheDocument();
  });

  it('opens create dialog when "Add Chart Source" is clicked', async () => {
    const user = userEvent.setup();
    renderPage();

    const addButton = screen.getByText('Add Chart Source');
    await user.click(addButton);

    const dialog = within(screen.getByRole('dialog'));
    expect(screen.getByText('Add Helm Chart Source')).toBeInTheDocument();
    expect(dialog.getByRole('textbox', { name: 'Name' })).toBeInTheDocument();
    expect(dialog.getByRole('textbox', { name: 'Repository URL' })).toBeInTheDocument();
    expect(dialog.getByRole('textbox', { name: 'Description' })).toBeInTheDocument();
  });

  it('submits the create form', async () => {
    mockCreateFn.mockReturnValue({ unwrap: () => Promise.resolve({ data: { id: 2 } }) });
    const user = userEvent.setup();
    renderPage();

    // Open dialog
    await user.click(screen.getByText('Add Chart Source'));

    const dialog = within(screen.getByRole('dialog'));

    // Fill the form
    await user.type(dialog.getByRole('textbox', { name: 'Name' }), 'bitnami');
    await user.type(
      dialog.getByRole('textbox', { name: 'Repository URL' }),
      'https://charts.bitnami.com/bitnami'
    );

    // Click Add
    await user.click(dialog.getByRole('button', { name: /^Add$/ }));

    expect(mockCreateFn).toHaveBeenCalledWith({
      name: 'bitnami',
      repo_url: 'https://charts.bitnami.com/bitnami',
      description: '',
    });
  });

  it('triggers re-index when Re-index button is clicked', async () => {
    const user = userEvent.setup();
    renderPage();

    // Находим кнопку Refresh (Re-index) по tooltip title
    const reindexButton = screen.getByRole('button', { name: /Re-index now/i });
    await user.click(reindexButton);

    expect(mockIndexFn).toHaveBeenCalledWith(1);
  });

  it('shows loading spinner when isLoading', () => {
    (useListHelmChartsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows empty state when no charts', () => {
    (useListHelmChartsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    renderPage();
    expect(screen.getByText(/No Helm chart sources yet/)).toBeInTheDocument();
  });
});
