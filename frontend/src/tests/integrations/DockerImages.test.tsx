import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { BrowserRouter } from 'react-router';
import { App } from 'antd';
import { DockerImagesPage } from '../../pages/DockerImages';
import { api } from '../../store/api';
import authReducer from '../../store/authSlice';
import { STATUS_FLAG } from '../../types';

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useListDockerImagesQuery: vi.fn(),
    useCreateDockerImageMutation: vi.fn(),
    useIndexDockerImageMutation: vi.fn(),
  };
});

import {
  useListDockerImagesQuery,
  useCreateDockerImageMutation,
  useIndexDockerImageMutation,
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

const mockSources = [
  {
    id: 1,
    name: 'Docker Hub',
    registry_url: 'https://registry-1.docker.io',
    description: 'Public Docker Hub registry',
    last_synced_at: '2026-02-01T12:00:00Z',
    status_flag: STATUS_FLAG.OK,
    status_text: 'Synced successfully',
    gitlab_project_id: null,
    gitlab_project_url: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-02-01T12:00:00Z',
  },
];

describe('DockerImagesPage', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    store = createTestStore();
    vi.clearAllMocks();
    mockCreateFn.mockReset();
    mockIndexFn.mockReset();
    (useListDockerImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockSources,
      isLoading: false,
      isError: false,
    });
    (useCreateDockerImageMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockCreateFn,
      { isLoading: false },
    ]);
    (useIndexDockerImageMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockIndexFn,
      { isLoading: false },
    ]);
  });

  function renderPage() {
    return render(
      <Provider store={store}>
        <BrowserRouter>
          <App>
            <DockerImagesPage />
          </App>
        </BrowserRouter>
      </Provider>
    );
  }

  it('renders the Docker Images heading', () => {
    renderPage();
    expect(screen.getByText('Docker Images')).toBeInTheDocument();
  });

  it('renders table with Name, Registry URL, and Status columns', () => {
    renderPage();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Registry URL')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();

    expect(screen.getByText('Docker Hub')).toBeInTheDocument();
    expect(screen.getByText('https://registry-1.docker.io')).toBeInTheDocument();
    expect(screen.getByText('Synced successfully')).toBeInTheDocument();
  });

  it('opens create dialog with optional image_name field', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByText('Add Registry'));

    const dialog = within(screen.getByRole('dialog'));
    expect(screen.getByText('Add Docker Registry')).toBeInTheDocument();
    // antd Input uses placeholder, not aria-label
    const imageNameInput = dialog.getByPlaceholderText('Image Name — optional (e.g. library/nginx)');
    expect(imageNameInput).toBeInTheDocument();

    // Name и Registry URL — antd required prop adds aria-required
    expect(dialog.getByPlaceholderText('Name (e.g. Docker Hub)').closest('input')).toBeRequired();
    expect(dialog.getByPlaceholderText('Registry URL (e.g. https://registry-1.docker.io)').closest('input')).toBeRequired();
  });

  it('submits create form with optional image_name', async () => {
    mockCreateFn.mockReturnValue({ unwrap: () => Promise.resolve({ data: { id: 2 } }) });
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByText('Add Registry'));

    const dialog = within(screen.getByRole('dialog'));

    await user.type(dialog.getByPlaceholderText('Name (e.g. Docker Hub)'), 'Private Hub');
    await user.type(
      dialog.getByPlaceholderText('Registry URL (e.g. https://registry-1.docker.io)'),
      'https://registry.example.com'
    );
    await user.type(dialog.getByPlaceholderText('Image Name — optional (e.g. library/nginx)'), 'library/nginx');

    await user.click(dialog.getByRole('button', { name: /^Add$/ }));

    expect(mockCreateFn).toHaveBeenCalledWith({
      name: 'Private Hub',
      registry_url: 'https://registry.example.com',
      description: undefined,
      image_name: 'library/nginx',
    });
  });

  it('submits create form without image_name', async () => {
    mockCreateFn.mockReturnValue({ unwrap: () => Promise.resolve({ data: { id: 2 } }) });
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByText('Add Registry'));

    const dialog = within(screen.getByRole('dialog'));

    await user.type(dialog.getByPlaceholderText('Name (e.g. Docker Hub)'), 'Private Hub');
    await user.type(
      dialog.getByPlaceholderText('Registry URL (e.g. https://registry-1.docker.io)'),
      'https://registry.example.com'
    );

    await user.click(dialog.getByRole('button', { name: /^Add$/ }));

    expect(mockCreateFn).toHaveBeenCalledWith({
      name: 'Private Hub',
      registry_url: 'https://registry.example.com',
      description: undefined,
      image_name: undefined,
    });
  });

  it('shows loading spinner when isLoading', () => {
    (useListDockerImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    const { container } = renderPage();
    // antd Spin renders with .ant-spin-spinning class
    expect(container.querySelector('.ant-spin-spinning')).toBeInTheDocument();
  });

  it('shows empty state when no sources', () => {
    (useListDockerImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    renderPage();
    expect(screen.getByText(/No Docker image sources yet/)).toBeInTheDocument();
  });
});
