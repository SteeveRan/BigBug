/**
 * @file Settings/Integrations/common.ts
 * @description Shared types, constants and utility functions used by all integration panels and dialogs.
 * @relatedFiles ./Gitlab.tsx, ./Harbor.tsx, ./Github.tsx, ./DockerRegistry.tsx, ./HelmRepository.tsx
 */

// ─── Constants ───────────────────────────────────────────────────────────────

export const TAB_LABELS = ['GitLab', 'Internal Registries', 'GitHub', 'External Registries', 'Helm Repository'] as const;

// ─── Dialog state ────────────────────────────────────────────────────────────

export interface DialogState {
  open: boolean;
  mode: 'add' | 'edit';
  instanceId?: number;
  defaultValues?: Record<string, unknown>;
}

export const EMPTY_DIALOG: DialogState = { open: false, mode: 'add' };

// ─── Form validation helpers ─────────────────────────────────────────────────

export function isValidUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

export interface FormErrors {
  name?: string;
  url?: string;
  username?: string;
  token?: string;
  password?: string;
  defaultGroupId?: string;
}

// ─── Panel props ─────────────────────────────────────────────────────────────

export interface PanelProps {
  showMessage: (message: string, severity: 'success' | 'error') => void;
}
