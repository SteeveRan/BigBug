/**
 * @file providersColumns.ts
 * @description Pure column-key ordering for the Providers page table. Tab-specific
 *              column sets are computed here so the domain/tab logic has a single
 *              testable point (see providersColumns.test.ts).
 */

import type { ProviderDomain } from '../../../types';

export type ProviderColumnKey =
  | 'label'
  | 'domain'
  | 'subtype'
  | 'category'
  | 'direction'
  | 'visibility'
  | 'status'
  | 'oci'
  | 'base_url'
  | 'default'
  | 'credential'
  | 'owner'
  | 'actions';

export interface ProviderColumnContext {
  activeTab: string;
  domain?: ProviderDomain;
}

export interface ProviderColumnGroup {
  all: ProviderColumnKey[];
  git: ProviderColumnKey[];
  docker: ProviderColumnKey[];
  helm: ProviderColumnKey[];
  mine: ProviderColumnKey[];
}

// "All" shows only common information; domain tabs add their domain-specific column.
// Management columns (default/credential) only appear on a concrete domain tab.
export const PROVIDER_COLUMN_GROUPS: ProviderColumnGroup = {
  all: [
    'label',
    'domain',
    'subtype',
    'category',
    'direction',
    'visibility',
    'status',
    'owner',
    'actions',
  ],
  git: [
    'label',
    'subtype',
    'category',
    'direction',
    'visibility',
    'status',
    'base_url',
    'default',
    'credential',
    'owner',
    'actions',
  ],
  docker: [
    'label',
    'subtype',
    'category',
    'direction',
    'visibility',
    'status',
    'oci',
    'default',
    'credential',
    'owner',
    'actions',
  ],
  helm: [
    'label',
    'subtype',
    'category',
    'direction',
    'visibility',
    'status',
    'base_url',
    'default',
    'credential',
    'owner',
    'actions',
  ],
  mine: [
    'label',
    'domain',
    'subtype',
    'category',
    'direction',
    'visibility',
    'status',
    'default',
    'credential',
    'owner',
    'actions',
  ],
};

/**
 * Resolve the ordered list of column keys for a tab + optional domain override.
 * The domain filter (Search row) takes precedence over the tab's implicit domain.
 */
export function resolveProviderColumns(ctx: ProviderColumnContext): ProviderColumnKey[] {
  const tabDomain = ctx.domain ?? domainForTab(ctx.activeTab);
  if (ctx.activeTab === 'all' && !ctx.domain) return PROVIDER_COLUMN_GROUPS.all;
  if (ctx.activeTab === 'mine' && !ctx.domain) return PROVIDER_COLUMN_GROUPS.mine;
  if (tabDomain) return PROVIDER_COLUMN_GROUPS[tabDomain];
  return PROVIDER_COLUMN_GROUPS.all;
}

function domainForTab(activeTab: string): ProviderDomain | undefined {
  switch (activeTab) {
    case 'git':
      return 'git';
    case 'docker':
      return 'docker';
    case 'helm':
      return 'helm';
    default:
      return undefined;
  }
}
