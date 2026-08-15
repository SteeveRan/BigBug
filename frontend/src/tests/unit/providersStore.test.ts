/**
 * @file providersStore.test.ts
 * @description Unit tests for Providers V3 RTK Query endpoints (existence + query/mutation kind).
 * @dependencies Vitest
 */

import { describe, it, expect } from 'vitest';
import { providersApi } from '../../store/api/providers';

describe('providersStore — endpoints', () => {
  it('registers all providers endpoints', () => {
    const names = Object.keys(providersApi.endpoints);
    for (const name of [
      'getProviderTypes',
      'getProviders',
      'getProvider',
      'createProvider',
      'updateProvider',
      'deleteProvider',
      'testProvider',
      'runProviderAction',
      'getProviderUsage',
      'shareProvider',
      'unshareProvider',
    ]) {
      expect(names).toContain(name);
    }
  });

  it('getProviderTypes is a query (has useQuery hook)', () => {
    const endpoint = providersApi.endpoints.getProviderTypes;
    expect(typeof endpoint.useQuery).toBe('function');
  });

  it('getProviders is a query (has useQuery hook)', () => {
    const endpoint = providersApi.endpoints.getProviders;
    expect(typeof endpoint.useQuery).toBe('function');
  });

  it('createProvider is a mutation (has useMutation hook)', () => {
    const endpoint = providersApi.endpoints.createProvider;
    expect(typeof endpoint.useMutation).toBe('function');
  });

  it('updateProvider is a mutation', () => {
    const endpoint = providersApi.endpoints.updateProvider;
    expect(typeof endpoint.useMutation).toBe('function');
  });

  it('deleteProvider is a mutation', () => {
    const endpoint = providersApi.endpoints.deleteProvider;
    expect(typeof endpoint.useMutation).toBe('function');
  });

  it('shareProvider/unshareProvider are mutations', () => {
    expect(typeof providersApi.endpoints.shareProvider.useMutation).toBe('function');
    expect(typeof providersApi.endpoints.unshareProvider.useMutation).toBe('function');
  });

  it('testProvider is a mutation and getProviderUsage is a query', () => {
    expect(typeof providersApi.endpoints.testProvider.useMutation).toBe('function');
    expect(typeof providersApi.endpoints.getProviderUsage.useQuery).toBe('function');
  });
});
