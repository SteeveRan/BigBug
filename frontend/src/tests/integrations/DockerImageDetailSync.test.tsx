import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { App } from 'antd';
import { MemoryRouter, Route, Routes } from 'react-router';
import { DockerImageDetailPage } from '../../pages/DockerImages/DockerImageDetail';
import { api } from '../../store/api';
import authReducer, { setPermissions } from '../../store/authSlice';
import { STATUS_FLAG } from '../../types';

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetDockerImageQuery: vi.fn(),
    useGetDockerImageTagsQuery: vi.fn(),
    useGetDockerImageLogsQuery: vi.fn(),
    useGetDockerSyncSchedulesQuery: vi.fn(),
    useSyncDockerImageMutation: vi.fn(),
    useIndexDockerImageMutation: vi.fn(),
    useUpdateDockerImageMutation: vi.fn(),
    useCreateDockerSyncScheduleMutation: vi.fn(),
    useUpdateDockerSyncScheduleMutation: vi.fn(),
    useDeleteDockerSyncScheduleMutation: vi.fn(),
    useBatchDeleteDockerTagsMutation: vi.fn(),
  };
});

import {
  useGetDockerImageQuery,
  useGetDockerImageTagsQuery,
  useGetDockerImageLogsQuery,
  useGetDockerSyncSchedulesQuery,
  useSyncDockerImageMutation,
  useIndexDockerImageMutation,
  useUpdateDockerImageMutation,
  useCreateDockerSyncScheduleMutation,
  useUpdateDockerSyncScheduleMutation,
  useDeleteDockerSyncScheduleMutation,
  useBatchDeleteDockerTagsMutation,
} from '../../store/api';

const mockSyncFn = vi.fn();

function createTestStore() {
  const store = configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
  store.dispatch(setPermissions(['docker:sync']));
  return store;
}

const sourceWithTarget = {
  id: 42,
  name: 'library/nginx',
  registry_url: 'https://registry-1.docker.io/v2',
  target_registry_url: 'https://harbor.example.com',
  target_project: 'bigbug',
  status_flag: STATUS_FLAG.OK,
  status_text: 'OK',
  description: null,
  last_synced_at: null,
  gitlab_project_id: null,
  gitlab_project_url: null,
};

const sourceWithoutTarget = {
  ...sourceWithTarget,
  target_registry_url: null,
  target_project: null,
};

const tags = [
  {
    id: 1,
    source_id: 42,
    image_name: 'library/nginx',
    tag: 'latest',
    status_flag: STATUS_FLAG.OK,
    size_bytes: null,
    digest: null,
    architectures: null,
  },
  {
    id: 2,
    source_id: 42,
    image_name: 'library/nginx',
    tag: '1.27-alpine',
    status_flag: STATUS_FLAG.OK,
    size_bytes: null,
    digest: null,
    architectures: null,
  },
];

function renderDetail(store: ReturnType<typeof createTestStore>) {
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/docker-images/42']}>
        <Routes>
          <Route
            path="/docker-images/:id"
            element={
              <App>
                <DockerImageDetailPage />
              </App>
            }
          />
        </Routes>
      </MemoryRouter>
    </Provider>
  );
}

describe('DockerImageDetailSync', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    store = createTestStore();
    vi.clearAllMocks();
    mockSyncFn.mockReset();
    (useGetDockerImageQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: sourceWithTarget,
      isLoading: false,
      isError: false,
    });
    (useGetDockerImageTagsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: tags,
      isLoading: false,
    });
    (useGetDockerImageLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
    });
    (useGetDockerSyncSchedulesQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
    });
    (useSyncDockerImageMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockSyncFn,
      { isLoading: false },
    ]);
    (useIndexDockerImageMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateDockerImageMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useCreateDockerSyncScheduleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useUpdateDockerSyncScheduleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useDeleteDockerSyncScheduleMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
    (useBatchDeleteDockerTagsMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      vi.fn(),
      { isLoading: false },
    ]);
  });

  it('shows the Sync button when the source has a target and permission is granted', () => {
    renderDetail(store);
    const syncButton = screen.getByRole('button', { name: /Синхронизировать/ });
    expect(syncButton).toBeInTheDocument();
    expect(syncButton).not.toBeDisabled();
  });

  it('disables the Sync button when the source has no target', () => {
    (useGetDockerImageQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: sourceWithoutTarget,
      isLoading: false,
      isError: false,
    });
    renderDetail(store);
    const syncButton = screen.getByRole('button', { name: /Синхронизировать/ });
    expect(syncButton).toBeDisabled();
  });

  it('opens the sync dialog and calls the mutation with the selected tag', async () => {
    const user = userEvent.setup();
    mockSyncFn.mockReturnValue({
      unwrap: () => Promise.resolve({ status_flag: STATUS_FLAG.OK }),
    });
    renderDetail(store);

    await user.click(screen.getByRole('button', { name: /Синхронизировать/ }));

    const dialog = within(screen.getByRole('dialog'));
    expect(dialog.getByText('Синхронизация образа')).toBeInTheDocument();

    // The tag Select is populated with the tags; click Sync to submit the
    // default (first) tag.
    await user.click(dialog.getByRole('button', { name: 'Синхронизировать' }));

    expect(mockSyncFn).toHaveBeenCalledWith({
      id: 42,
      image_name: 'library/nginx',
      tag: 'latest',
    });
  });

  it('hides the Sync button without docker:sync permission', () => {
    store.dispatch(setPermissions([]));
    renderDetail(store);
    expect(screen.queryByRole('button', { name: /Синхронизировать/ })).not.toBeInTheDocument();
  });
});
