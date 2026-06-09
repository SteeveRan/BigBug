import { createSlice, PayloadAction } from '@reduxjs/toolkit';

/**
 * Декодирует JWT токен и извлекает массив permissions.
 *
 * Использует только безопасные методы: atob(), JSON.parse().
 * НЕ применяет eval() или Function().
 *
 * @param token - JWT access token в формате header.payload.signature
 * @returns массив строк permissions или [] при ошибке/отсутствии
 */
function parseJwtPermissions(token: string): string[] {
  try {
    const base64Payload = token.split('.')[1];
    const jsonPayload = atob(base64Payload);
    const payload = JSON.parse(jsonPayload);
    return Array.isArray(payload.permissions) ? payload.permissions : [];
  } catch {
    return [];
  }
}

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  roles: string[];
  is_active: boolean;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  /** RBAC permissions extracted from JWT (populated in Phase 2) */
  permissions: string[];
}

const initialState: AuthState = {
  user: null,
  accessToken: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: false,
  permissions: parseJwtPermissions(localStorage.getItem('access_token') || ''),
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setCredentials: (
      state,
      action: PayloadAction<{ accessToken: string; refreshToken: string; user: AuthUser }>
    ) => {
      state.accessToken = action.payload.accessToken;
      state.refreshToken = action.payload.refreshToken;
      state.user = action.payload.user;
      state.isAuthenticated = true;
      state.permissions = parseJwtPermissions(action.payload.accessToken);
      localStorage.setItem('access_token', action.payload.accessToken);
      localStorage.setItem('refresh_token', action.payload.refreshToken);
    },
    setUser: (state, action: PayloadAction<AuthUser>) => {
      state.user = action.payload;
      state.isAuthenticated = true;
    },
    logout: (state) => {
      state.user = null;
      state.accessToken = null;
      state.refreshToken = null;
      state.isAuthenticated = false;
      state.permissions = [];
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },
  },
});

export const { setCredentials, setUser, logout, setLoading } = authSlice.actions;
export default authSlice.reducer;

/** Selector: returns the RBAC permissions string[] from auth state */
export const selectUserPermissions = (state: { auth: AuthState }) => state.auth.permissions;
