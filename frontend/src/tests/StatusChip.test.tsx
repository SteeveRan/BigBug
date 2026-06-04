import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusChip } from '../components/StatusChip'
import { STATUS_FLAG } from '../types'

describe('StatusChip', () => {
  it('renders OK status', () => {
    render(<StatusChip statusFlag={STATUS_FLAG.OK} />)
    expect(screen.getByText('OK')).toBeInTheDocument()
  })

  it('renders Failed status', () => {
    render(<StatusChip statusFlag={STATUS_FLAG.FAILED} />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('renders custom status text', () => {
    render(<StatusChip statusFlag={STATUS_FLAG.IN_PROGRESS} statusText="running pipeline" />)
    expect(screen.getByText('running pipeline')).toBeInTheDocument()
  })

  it('renders Pending status', () => {
    render(<StatusChip statusFlag={STATUS_FLAG.PENDING} />)
    expect(screen.getByText('Pending')).toBeInTheDocument()
  })

  it('renders Warning status', () => {
    render(<StatusChip statusFlag={STATUS_FLAG.WARNING} />)
    expect(screen.getByText('Warning')).toBeInTheDocument()
  })
})
