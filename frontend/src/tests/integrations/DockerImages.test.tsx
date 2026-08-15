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
    useAnalyzeDockerImageMutation: vi.fn(),
    useIndexDockerImageMutation: vi.fn(),
  };
});

import {
  useListDockerImagesQuery,
  useCreateDockerImageMutation,
  useAnalyzeDockerImageMutation,
  useIndexDockerImageMutation,
} from '../../store/api';

const mockCreateFn = vi.fn();
const mockAnalyzeFn = vi.fn();
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
    mockAnalyzeFn.mockReset();
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
    (useAnalyzeDockerImageMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockAnalyzeFn,
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

  it('renders table with Name, Registry URL, and Mirroring Status columns', () => {
    renderPage();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Registry URL')).toBeInTheDocument();
    expect(screen.getByText('Mirroring Status')).toBeInTheDocument();

    expect(screen.getByText('Docker Hub')).toBeInTheDocument();
    expect(screen.getByText('https://registry-1.docker.io')).toBeInTheDocument();
  });

  const mockAnalysisResponse = {
    image_name: 'library/nginx',
    normalized_image: 'library/nginx:latest',
    detected_registry_host: 'docker.io',
    detected_provider: 'docker_hub',
    compatible_registries: [
      {
        id: 1,
        domain: 'docker',
        subtype: 'docker_hub',
        category: 'public',
        direction: 'external',
        name: 'Docker Hub',
        label: 'Docker Hub',
        base_url: 'https://registry-1.docker.io',
      },
    ],
    suggested_registry: {
      id: 1,
      domain: 'docker',
      subtype: 'docker_hub',
      category: 'public',
      direction: 'external',
      name: 'Docker Hub',
      label: 'Docker Hub',
      base_url: 'https://registry-1.docker.io',
    },
    is_new_registry_needed: false,
  };

  it('opens dialog with two-step Add Image flow', async () => {
    const user = userEvent.setup();
    renderPage();

    // Click "Add Image" button (new UI)
    await user.click(screen.getByRole('button', { name: /Add Image/ }));

    const dialog = within(screen.getByRole('dialog'));
    expect(screen.getByText('Add Docker Image')).toBeInTheDocument();

    // Step 1: image name input + Analyze button
    const imageInput = dialog.getByPlaceholderText(
      'e.g. nginx:latest or quay.io/prometheus/node-exporter:latest'
    );
    expect(imageInput).toBeInTheDocument();
    expect(dialog.getByRole('button', { name: 'Analyze' })).toBeDisabled();
  });

  it('analyzes image and completes two-step creation flow', async () => {
    mockAnalyzeFn.mockReturnValue({ unwrap: () => Promise.resolve(mockAnalysisResponse) });
    mockCreateFn.mockReturnValue({ unwrap: () => Promise.resolve({ data: { id: 2 } }) });
    const user = userEvent.setup();
    renderPage();

    // Click "Add Image" button
    await user.click(screen.getByRole('button', { name: /Add Image/ }));

    const dialog = within(screen.getByRole('dialog'));

    // Step 1: enter image name
    await user.type(
      dialog.getByPlaceholderText('e.g. nginx:latest or quay.io/prometheus/node-exporter:latest'),
      'library/nginx:latest'
    );

    // Click Analyze
    await user.click(dialog.getByRole('button', { name: 'Analyze' }));

    // Verify analyze mutation was called
    expect(mockAnalyzeFn).toHaveBeenCalledWith({ image_name: 'library/nginx:latest' });

    // Step 2 should show: we need to wait for the UI to update after the promise resolves
    // The Select and "Add Image" button should appear
    expect(await dialog.findByText('Normalized Image')).toBeInTheDocument();
    expect(dialog.getByText('library/nginx:latest')).toBeInTheDocument();
    expect(dialog.getByText('Detected Registry')).toBeInTheDocument();

    // Click "Add Image" to submit
    await user.click(dialog.getByRole('button', { name: 'Add Image' }));

    // Verify create mutation was called with analysis-derived fields
    expect(mockCreateFn).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'library/nginx',
        registry_url: 'https://registry-1.docker.io',
        image_name: 'library/nginx:latest',
        provider_id: 1,
      })
    );
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
