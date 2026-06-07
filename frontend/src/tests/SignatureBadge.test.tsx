/**
 * @file SignatureBadge.test.tsx
 * @description Unit tests for the SignatureBadge component
 * @dependencies Vitest, @testing-library/react
 * @relatedFiles ../components/SignatureBadge.tsx
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SignatureBadge } from '../components/SignatureBadge';

describe('SignatureBadge', () => {
  it('shows "Signed" when isSigned is true', () => {
    render(<SignatureBadge isSigned={true} />);
    expect(screen.getByText(/signed/i)).toBeInTheDocument();
  });

  it('shows "Unsigned" when isSigned is false', () => {
    render(<SignatureBadge isSigned={false} />);
    expect(screen.getByText(/unsigned/i)).toBeInTheDocument();
  });

  it('renders with signature prop', () => {
    render(<SignatureBadge isSigned={true} signature="cosign:v1" />);
    expect(screen.getByText(/signed/i)).toBeInTheDocument();
  });

  it('renders unsigned with null signature', () => {
    render(<SignatureBadge isSigned={false} signature={null} />);
    expect(screen.getByText(/unsigned/i)).toBeInTheDocument();
  });
});
