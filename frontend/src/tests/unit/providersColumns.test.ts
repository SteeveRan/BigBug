/**
 * @file providersColumns.test.ts
 * @description Unit tests for the Providers page column-key resolution.
 */

import { describe, it, expect } from 'vitest';
import {
  resolveProviderColumns,
  PROVIDER_COLUMN_GROUPS,
} from '../../pages/Settings/Providers/providersColumns';

describe('resolveProviderColumns', () => {
  it('shows only common information on the All tab', () => {
    const keys = resolveProviderColumns({ activeTab: 'all' });
    expect(keys).toEqual(PROVIDER_COLUMN_GROUPS.all);
    expect(keys).not.toContain('oci');
    expect(keys).not.toContain('base_url');
    expect(keys).not.toContain('default');
    expect(keys).not.toContain('credential');
  });

  it('adds the OCI column on the docker tab', () => {
    const keys = resolveProviderColumns({ activeTab: 'docker' });
    expect(keys).toContain('oci');
    expect(keys).not.toContain('base_url');
  });

  it('adds the base URL column on the git tab', () => {
    const keys = resolveProviderColumns({ activeTab: 'git' });
    expect(keys).toContain('base_url');
    expect(keys).not.toContain('oci');
  });

  it('adds the base URL column on the helm tab', () => {
    const keys = resolveProviderColumns({ activeTab: 'helm' });
    expect(keys).toContain('base_url');
    expect(keys).not.toContain('oci');
  });

  it('keeps the domain column when a domain filter overrides the All tab', () => {
    const keys = resolveProviderColumns({ activeTab: 'all', domain: 'docker' });
    expect(keys).toContain('oci');
    expect(keys).not.toContain('domain');
  });

  it('applies the domain filter override over the tab domain', () => {
    const keys = resolveProviderColumns({ activeTab: 'git', domain: 'helm' });
    expect(keys).toContain('base_url');
    expect(keys).not.toContain('oci');
  });
});
