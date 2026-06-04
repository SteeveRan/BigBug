import { Chip } from '@mui/material'
import { STATUS_FLAG, StatusFlag } from '../types'

interface StatusChipProps {
  statusFlag: StatusFlag
  statusText?: string | null
  size?: 'small' | 'medium'
}

const STATUS_CONFIG: Record<StatusFlag, { label: string; color: 'success' | 'error' | 'warning' | 'info' | 'default' }> = {
  [STATUS_FLAG.OK]: { label: 'OK', color: 'success' },
  [STATUS_FLAG.FAILED]: { label: 'Failed', color: 'error' },
  [STATUS_FLAG.WARNING]: { label: 'Warning', color: 'warning' },
  [STATUS_FLAG.IN_PROGRESS]: { label: 'Running', color: 'info' },
  [STATUS_FLAG.PENDING]: { label: 'Pending', color: 'default' },
}

export function StatusChip({ statusFlag, statusText, size = 'small' }: StatusChipProps) {
  const config = STATUS_CONFIG[statusFlag] ?? { label: 'Unknown', color: 'default' as const }
  return (
    <Chip
      label={statusText ?? config.label}
      color={config.color}
      size={size}
      variant="outlined"
    />
  )
}
