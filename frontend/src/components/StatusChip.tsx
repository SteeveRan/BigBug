/**
 * @file StatusChip.tsx
 * @description Displays a status badge using Ant Design Tag.
 *              Supports numeric status 0-4 with colour mapping.
 *
 * @dependencies antd
 * @relatedFiles ../types/index.ts
 */
import { Tag } from 'antd';

interface StatusChipProps {
  /** New API: numeric status 0–4 */
  status?: number;
  /** Optional custom label map (status → text) */
  labels?: Record<number, string>;
  // ── Backward-compatible (old) props ──────────────────────────────────────
  statusFlag?: number;
  statusText?: string | null;
  size?: 'small' | 'medium';
}

const DEFAULT_LABELS: Record<number, string> = {
  0: 'OK',
  1: 'Failed',
  2: 'Warning',
  3: 'In Progress',
  4: 'Pending',
};

const STATUS_COLORS: Record<number, string> = {
  0: 'success',
  1: 'error',
  2: 'warning',
  3: 'processing',
  4: 'default',
};

export function StatusChip({
  status,
  labels,
  statusFlag,
  statusText,
}: StatusChipProps) {
  const effectiveStatus = status ?? statusFlag ?? 4;
  const labelMap = labels ?? DEFAULT_LABELS;
  const color = STATUS_COLORS[effectiveStatus] ?? 'default';
  const text = statusText ?? labelMap[effectiveStatus] ?? 'Unknown';

  return <Tag color={color}>{text}</Tag>;
}

export default StatusChip;
