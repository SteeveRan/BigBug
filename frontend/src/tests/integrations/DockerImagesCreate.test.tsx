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

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useListDockerImagesQuery: vi.fn(),
    useCreateDockerImageMutation: vi.fn(),
    useAnalyzeDockerImageMutation: vi.fn(),
  };
});

import {
  useListDockerImagesQuery,
  useCreateDockerImageMutation,
  useAnalyzeDockerImageMutation,
} from '../../store/api';

const mockCreateFn = vi.fn();
const mockAnalyzeFn = vi.fn();

function createTestStore() {
  return configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

const harborTarget = {
  id: 7,
  domain: 'docker',
  subtype: 'harbor',
  category: 'system',
  direction: 'internal',
  name: 'harbor-system',
  label: 'Harbor (system)',
  base_url: 'https://harbor.example.com',
  config: { default_project: 'bigbug' },
  is_default: true,
};

const dockerHubSource = {
  id: 1,
  domain: 'docker',
  subtype: 'docker_hub',
  category: 'public',
  direction: 'external',
  name: 'Docker Hub',
  label: 'Docker Hub',
  base_url: 'https://registry-1.docker.io',
  config: {},
};

function analysisWithTargets(availableTargets: unknown[]) {
  return {
    image_name: 'library/nginx',
    normalized_image: 'library/nginx:latest',
    detected_registry_host: 'docker.io',
    detected_provider: 'docker_hub',
    compatible_registries: [dockerHubSource],
    suggested_registry: dockerHubSource,
    is_new_registry_needed: false,
    available_targets: availableTargets,
    repository_path: 'library/nginx',
  };
}

describe('DockerImagesCreate', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    store = createTestStore();
    vi.clearAllMocks();
    mockCreateFn.mockReset();
    mockAnalyzeFn.mockReset();
    (useListDockerImagesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
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

  async function openAndAnalyze() {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole('button', { name: /Add Image/ }));
    const dialog = within(screen.getByRole('dialog'));
    await user.type(
      dialog.getByPlaceholderText(
        'e.g. nginx:latest or quay.io/prometheus/node-exporter:latest'
      ),
      'library/nginx:latest'
    );
    await user.click(dialog.getByRole('button', { name: 'Analyze' }));
    return { user, dialog: within(screen.getByRole('dialog')) };
  }

  it('renders both source and target selects when targets exist', async () => {
    mockAnalyzeFn.mockReturnValue({
      unwrap: () => Promise.resolve(analysisWithTargets([harborTarget])),
    });

    const { dialog } = await openAndAnalyze();

    expect(await dialog.findByText('Source Registry')).toBeInTheDocument();
    expect(dialog.getByText('Mirror Target')).toBeInTheDocument();
  });

  it('sends target fields and repository_path in the create payload', async () => {
    mockAnalyzeFn.mockReturnValue({
      unwrap: () => Promise.resolve(analysisWithTargets([harborTarget])),
    });
    mockCreateFn.mockReturnValue({ unwrap: () => Promise.resolve({ id: 9 }) });

    const { user, dialog } = await openAndAnalyze();

    expect(await dialog.findByText('Mirror Target')).toBeInTheDocument();

    // antd Select interactions: click the target select then pick the option.
    const targetSelect = dialog.getByText('Mirror Target').closest('div')?.parentElement;
    expect(targetSelect).toBeTruthy();

    await user.click(dialog.getByRole('button', { name: 'Add Image' }));

    expect(mockCreateFn).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'library/nginx',
        image_name: 'library/nginx',
        provider_id: 1,
        target_provider_id: 7,
        target_registry_url: 'https://harbor.example.com',
        target_project: 'bigbug',
      })
    );
  });

  it('shows a warning when there are no available targets', async () => {
    mockAnalyzeFn.mockReturnValue({
      unwrap: () => Promise.resolve(analysisWithTargets([])),
    });

    const { dialog } = await openAndAnalyze();

    expect(
      await dialog.findByText(/No internal Harbor target configured/)
    ).toBeInTheDocument();
  });
});
