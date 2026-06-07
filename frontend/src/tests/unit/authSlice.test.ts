import { describe, it, expect } from 'vitest';
import authReducer, { setCredentials, setUser, logout, AuthUser } from '../../store/authSlice';

const mockUser: AuthUser = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  roles: ['operator'],
  is_active: true,
};

describe('authSlice', () => {
  it('should return initial state', () => {
    const state = authReducer(undefined, { type: 'unknown' });
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });

  it('should set credentials', () => {
    const state = authReducer(
      undefined,
      setCredentials({
        accessToken: 'access123',
        refreshToken: 'refresh123',
        user: mockUser,
      })
    );
    expect(state.accessToken).toBe('access123');
    expect(state.refreshToken).toBe('refresh123');
    expect(state.user).toEqual(mockUser);
    expect(state.isAuthenticated).toBe(true);
  });

  it('should set user', () => {
    const state = authReducer(undefined, setUser(mockUser));
    expect(state.user).toEqual(mockUser);
    expect(state.isAuthenticated).toBe(true);
  });

  it('should logout', () => {
    const loggedInState = authReducer(
      undefined,
      setCredentials({
        accessToken: 'access123',
        refreshToken: 'refresh123',
        user: mockUser,
      })
    );
    const state = authReducer(loggedInState, logout());
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });
});
