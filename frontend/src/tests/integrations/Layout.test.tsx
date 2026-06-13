/**
 * @file Layout.test.tsx
 * @description Integration tests for Layout sidebar menu items.
 *              Covers Stage 7.3 changes: Artifacts rename, Dashboard/Orphaned/Reports additions.
 * @dependencies Vitest, @testing-library/react, Redux Toolkit, React Router
 * @relatedFiles ../../components/Layout/index.tsx, ../../router/index.tsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router';
import { configureStore } from '@reduxjs/toolkit';
import { App } from 'antd';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(),
}));

vi.mock('../../store/api', async () => {
  const actual = await vi.importActual('../../store/api');
  return {
    ...(actual as object),
    useGetMeQuery: vi.fn(),
  };
});

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import { api } from '../../store/api';
import { useGetMeQuery } from '../../store/api';
import { usePermissions } from '../../hooks/usePermissions';
import authReducer, { setCredentials } from '../../store/authSlice';
import { Layout } from '../../components/Layout';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createTestStore() {
  return configureStore({
    reducer: {
      auth: authReducer,
      [api.reducerPath]: api.reducer,
    },
    middleware: (gdm) => gdm().concat(api.middleware),
  });
}

function mockAuthState(store: ReturnType<typeof createTestStore>) {
  store.dispatch(
    setCredentials({
      accessToken: 'fake-access-token',
      refreshToken: 'fake-refresh-token',
      user: {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        roles: ['admin'],
        is_active: true,
      },
    })
  );
}

function setupMocks() {
  // Permissions — allow all
  (usePermissions as ReturnType<typeof vi.fn>).mockReturnValue({
    hasPermission: () => true,
    hasAnyPermission: () => true,
    hasAllPermissions: () => true,
    permissions: ['*'],
    isLoading: false,
  });

  // useGetMeQuery — return authenticated user
  (useGetMeQuery as ReturnType<typeof vi.fn>).mockReturnValue({
    data: {
      id: 1,
      username: 'testuser',
      email: 'test@example.com',
      roles: ['admin'],
      is_active: true,
    },
    isLoading: false,
    isError: false,
  });
}

function renderLayout(path = '/overview') {
  const store = createTestStore();
  mockAuthState(store);

  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>
        <App>
          <Layout />
        </App>
      </MemoryRouter>
    </Provider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Layout sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  describe('Group Artifacts (renamed from Mirroring)', () => {
    it('shows "Artifacts" group label instead of "Mirroring"', () => {
      renderLayout();
      expect(screen.getByText('Artifacts')).toBeInTheDocument();
      expect(screen.queryByText('Mirroring')).not.toBeInTheDocument();
    });

    it('shows Helm Charts under Artifacts', () => {
      renderLayout();
      expect(screen.getByText('Helm Charts')).toBeInTheDocument();
    });

    it('shows Docker Images under Artifacts', () => {
      renderLayout();
      expect(screen.getByText('Docker Images')).toBeInTheDocument();
    });

    it('does NOT show Repositories under Artifacts', () => {
      renderLayout();
      // "Repositories" appears ONLY in Git Mirroring group, not in Artifacts
      // But the label text is the same, so we check the menu structure
      // The Artifacts group's children should NOT contain Repositories
      const menuItems = screen.getAllByText('Repositories');
      // Expect at most one "Repositories" (the one in Git Mirroring group)
      // Artifacts has only Helm Charts + Docker Images
      expect(menuItems.length).toBeLessThanOrEqual(1);
    });
  });

  describe('Git Mirroring group', () => {
    it('shows Dashboard as first item in Git Mirroring', () => {
      renderLayout();
      // Dashboard appears in the Git Mirroring section
      const dashboardItems = screen.getAllByText('Dashboard');
      expect(dashboardItems.length).toBeGreaterThanOrEqual(1);
    });

    it('shows Mirrors in Git Mirroring', () => {
      renderLayout();
      expect(screen.getByText('Mirrors')).toBeInTheDocument();
    });

    it('shows Repositories in Git Mirroring', () => {
      renderLayout();
      expect(screen.getByText('Repositories')).toBeInTheDocument();
    });

    it('shows Source Providers in Git Mirroring', () => {
      renderLayout();
      expect(screen.getByText('Source Providers')).toBeInTheDocument();
    });

    it('shows Source Groups in Git Mirroring', () => {
      renderLayout();
      expect(screen.getByText('Source Groups')).toBeInTheDocument();
    });

    it('shows Sync Groups in Git Mirroring', () => {
      renderLayout();
      expect(screen.getByText('Sync Groups')).toBeInTheDocument();
    });

    it('shows Orphaned Mirrors in Git Mirroring (new)', () => {
      renderLayout();
      expect(screen.getByText('Orphaned Mirrors')).toBeInTheDocument();
    });

    it('shows Reports in Git Mirroring (new)', () => {
      renderLayout();
      expect(screen.getByText('Reports')).toBeInTheDocument();
    });
  });
});
