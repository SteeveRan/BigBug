import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { SsoCallbackPage } from '../pages/SsoCallback'
import { api } from '../store/api'
import authReducer from '../store/authSlice'

// Mock react-router
const mockNavigate = vi.fn()
vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
}))

// Mock useKeycloakAuth
const mockHandleCallback = vi.fn()
vi.mock('../hooks/useKeycloakAuth', () => ({
  useKeycloakAuth: () => ({
    ready: true,
    enabled: true,
    error: null,
    login: vi.fn(),
    handleCallback: mockHandleCallback,
  }),
}))

// Create a minimal store for the Provider
function createTestStore() {
  return configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  })
}

describe('SsoCallbackPage', () => {
  let store: ReturnType<typeof createTestStore>

  beforeEach(() => {
    store = createTestStore()
    vi.clearAllMocks()
    // Mock global fetch for /api/auth/me
    globalThis.fetch = vi.fn()
  })

  function renderPage() {
    return render(
      <Provider store={store}>
        <SsoCallbackPage />
      </Provider>,
    )
  }

  it('renders a loading spinner (CircularProgress)', () => {
    // Successful payload — component will attempt exchange
    mockHandleCallback.mockReturnValue({
      code: 'test-code',
      redirect_uri: 'https://app.example.com/sso/callback',
      code_verifier: 'test-verifier',
    })

    renderPage()

    // CircularProgress renders a <span> with role="progressbar"
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    expect(screen.getByText('Completing sign in…')).toBeInTheDocument()
  })

  it('redirects to /login when handleCallback returns an error', () => {
    mockHandleCallback.mockReturnValue({
      error: 'access_denied — user cancelled',
    })

    renderPage()

    expect(mockNavigate).toHaveBeenCalledWith(
      '/login?error=access_denied%20%E2%80%94%20user%20cancelled',
      { replace: true },
    )
  })

  it('redirects to /login when code is missing', () => {
    mockHandleCallback.mockReturnValue({
      error: 'Authorization code missing from callback URL',
    })

    renderPage()

    expect(mockNavigate).toHaveBeenCalledWith(
      expect.stringContaining('/login?error='),
      { replace: true },
    )
  })

  it('guards against double invocation in React StrictMode (useRef guard)', () => {
    // First call returns a valid payload
    mockHandleCallback.mockReturnValue({
      code: 'test-code',
      redirect_uri: 'https://app.example.com/sso/callback',
      code_verifier: 'test-verifier',
    })

    const { rerender } = render(
      <Provider store={store}>
        <SsoCallbackPage />
      </Provider>,
    )

    // Simulate StrictMode double-mount: rerender forces a second effect run
    // but the useRef guard prevents the second handleCallback() call.
    rerender(
      <Provider store={store}>
        <SsoCallbackPage />
      </Provider>,
    )

    // handleCallback should only have been called once (the ref guard works).
    expect(mockHandleCallback).toHaveBeenCalledTimes(1)
  })
})
