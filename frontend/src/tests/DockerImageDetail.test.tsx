import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { DockerImageDetailPage } from '../pages/DockerImages/DockerImageDetail'
import { api } from '../store/api'
import authReducer from '../store/authSlice'
import { STATUS_FLAG } from '../types'

// Mock react-router
const mockNavigate = vi.fn()
vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ id: '1' }),
  Link: ({ children, ...props }: any) => <a {...props}>{children}</a>,
}))

// Mock RTK Query hooks
vi.mock('../store/api', async () => {
  const actual = await vi.importActual('../store/api')
  return {
    ...(actual as object),
    useGetDockerImageQuery: vi.fn(),
    useGetDockerImageTagsQuery: vi.fn(),
    useGetDockerImageLogsQuery: vi.fn(),
    useIndexDockerImageMutation: vi.fn(),
  }
})

import {
  useGetDockerImageQuery,
  useGetDockerImageTagsQuery,
  useGetDockerImageLogsQuery,
  useIndexDockerImageMutation,
} from '../store/api'

const mockIndexFn = vi.fn()

function createTestStore() {
  return configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  })
}

const mockSource = {
  id: 1,
  name: 'Docker Hub',
  registry_url: 'https://registry-1.docker.io',
  description: 'Official Docker Hub images',
  last_synced_at: '2026-04-01T10:00:00Z',
  status_flag: STATUS_FLAG.OK,
  status_text: 'OK',
  gitlab_project_id: null,
  gitlab_project_url: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-04-01T10:00:00Z',
}

const mockTags = [
  {
    id: 20,
    source_id: 1,
    image_name: 'library/nginx',
    tag: '1.25-alpine',
    digest: 'sha256:def456',
    size_bytes: 43678901, // ~41.6 MB
    architectures: 'amd64,arm64',
    is_synced: true,
    status_flag: STATUS_FLAG.OK,
    status_text: 'Synced',
    last_synced_at: '2026-04-01T10:00:00Z',
    created_at: '2026-04-01T10:00:00Z',
  },
  {
    id: 21,
    source_id: 1,
    image_name: 'library/nginx',
    tag: 'latest',
    digest: 'sha256:ghi789',
    size_bytes: 1024, // 1 KB
    architectures: 'amd64',
    is_synced: true,
    status_flag: STATUS_FLAG.OK,
    status_text: 'Synced',
    last_synced_at: '2026-04-01T10:00:00Z',
    created_at: '2026-04-01T10:00:00Z',
  },
  {
    id: 22,
    source_id: 1,
    image_name: 'library/alpine',
    tag: '3.19',
    digest: 'sha256:jkl012',
    size_bytes: null, // unknown size
    architectures: 'amd64',
    is_synced: false,
    status_flag: STATUS_FLAG.PENDING,
    status_text: 'Pending',
    last_synced_at: null,
    created_at: '2026-04-01T10:00:00Z',
  },
]

const mockLogs = [
  {
    id: 200,
    source_id: 1,
    pipeline_id: '54321',
    pipeline_url: 'https://gitlab.example.com/pipelines/54321',
    status_flag: STATUS_FLAG.OK,
    status_text: 'Indexed 5 tags',
    log_output: null,
    triggered_by: 'system',
    started_at: '2026-04-01T10:00:00Z',
    finished_at: '2026-04-01T10:01:30Z',
    created_at: '2026-04-01T10:00:00Z',
  },
]

describe('DockerImageDetailPage', () => {
  let store: ReturnType<typeof createTestStore>

  beforeEach(() => {
    store = createTestStore()
    vi.clearAllMocks()
    mockIndexFn.mockReset()

    ;(useGetDockerImageQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockSource,
      isLoading: false,
      isError: false,
    })
    ;(useGetDockerImageTagsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockTags,
      isLoading: false,
      isError: false,
    })
    ;(useGetDockerImageLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockLogs,
      isLoading: false,
      isError: false,
    })
    ;(useIndexDockerImageMutation as ReturnType<typeof vi.fn>).mockReturnValue([
      mockIndexFn,
      { isLoading: false },
    ])
  })

  function renderPage() {
    return render(
      <Provider store={store}>
        <DockerImageDetailPage />
      </Provider>,
    )
  }

  it('renders source name as heading', () => {
    renderPage()
    expect(screen.getByText('Docker Hub')).toBeInTheDocument()
  })

  it('renders source info card with registry_url and status', () => {
    renderPage()
    expect(screen.getByText('Source Info')).toBeInTheDocument()
    expect(screen.getByText('https://registry-1.docker.io')).toBeInTheDocument()
    expect(screen.getByText('OK')).toBeInTheDocument()
  })

  it('renders tags table with Image, Tag, Architecture, Size columns', () => {
    renderPage()
    expect(screen.getByText('Image Tags (3)')).toBeInTheDocument()
    expect(screen.getByText('Image')).toBeInTheDocument()
    expect(screen.getByText('Tag')).toBeInTheDocument()
    expect(screen.getByText('Architecture')).toBeInTheDocument()
    expect(screen.getByText('Size')).toBeInTheDocument()

    // Tag data
    expect(screen.getByText('1.25-alpine')).toBeInTheDocument()
    expect(screen.getByText('latest')).toBeInTheDocument()
    expect(screen.getByText('3.19')).toBeInTheDocument()
    // library/nginx appears in two rows; use getAllByText
    expect(screen.getAllByText('library/nginx').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('amd64,arm64')).toBeInTheDocument()
  })

  it('formats bytes to human-readable (KB, MB)', () => {
    renderPage()
    // 1024 bytes → 1.0 KB
    expect(screen.getByText('1.0 KB')).toBeInTheDocument()
    // 43678901 bytes → ~41.6 MB
    expect(screen.getByText('41.7 MB')).toBeInTheDocument()
  })

  it('shows em dash for null size', () => {
    renderPage()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders sync logs table', () => {
    renderPage()
    expect(screen.getByText('Sync History')).toBeInTheDocument()
    expect(screen.getByText('system')).toBeInTheDocument()
    expect(screen.getByText('Indexed 5 tags')).toBeInTheDocument()
  })

  it('opens Index Image dialog and submits image_name', async () => {
    mockIndexFn.mockReturnValue({ unwrap: () => Promise.resolve({ data: { success: true } }) })
    const user = userEvent.setup()
    renderPage()

    // Click "Index Image" button
    await user.click(screen.getByText('Index Image'))

    // Dialog should appear
    const dialog = within(screen.getByRole('dialog'))
    expect(screen.getByText('Index Image Tags')).toBeInTheDocument()
    expect(dialog.getByRole('textbox', { name: 'Image Name' })).toBeInTheDocument()

    // Fill image name
    await user.type(dialog.getByRole('textbox', { name: 'Image Name' }), 'library/redis')

    // Submit
    await user.click(dialog.getByRole('button', { name: /^Index$/ }))

    expect(mockIndexFn).toHaveBeenCalledWith({
      id: 1,
      image_name: 'library/redis',
    })
  })

  it('disables Index button when image_name is empty', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText('Index Image'))

    const dialog = within(screen.getByRole('dialog'))
    const indexButton = dialog.getByRole('button', { name: /^Index$/ })
    expect(indexButton).toBeDisabled()
  })

  it('shows loading spinner when isLoading', () => {
    ;(useGetDockerImageQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    })

    renderPage()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('shows not found when source is null', () => {
    ;(useGetDockerImageQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
    })

    renderPage()
    expect(screen.getByText('Docker image source not found')).toBeInTheDocument()
  })

  it('shows empty tags message', () => {
    ;(useGetDockerImageTagsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    })

    renderPage()
    expect(screen.getByText(/No tags indexed yet/)).toBeInTheDocument()
  })

  it('shows empty logs message', () => {
    ;(useGetDockerImageLogsQuery as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    })

    renderPage()
    expect(screen.getByText('No sync history yet')).toBeInTheDocument()
  })
})
