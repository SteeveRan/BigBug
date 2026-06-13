import '@testing-library/jest-dom';
import { vi } from 'vitest';

// ---------------------------------------------------------------------------
// jsdom polyfills for antd / rc-* components
// ---------------------------------------------------------------------------

// Mock ThemeContext — used by Layout (Menu theme, headerBg) and theme-aware components
vi.mock('../../contexts/ThemeContext', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('../../hooks/useThemeMode', () => ({
  useThemeMode: () => ({
    mode: 'dark' as const,
    toggleTheme: vi.fn(),
  }),
}));

// antd Grid / useBreakpoint uses window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// rc-table uses window.getComputedStyle for scrollbar size detection.
// jsdom throws "Not implemented" — replace with a stub that returns
// reasonable defaults. Must include getPropertyValue() because
// dom-accessibility-api (used by @testing-library) calls it.
function createStyleStub(): CSSStyleDeclaration {
  const style: Record<string, string> = {
    borderRightWidth: '0px',
    borderLeftWidth: '0px',
    paddingRight: '0px',
    paddingLeft: '0px',
    width: '0px',
    height: '0px',
    display: 'block',
    visibility: 'visible',
  };

  return {
    getPropertyValue(prop: string): string {
      return style[prop] || '';
    },
    getPropertyPriority(): string {
      return '';
    },
    removeProperty(): string {
      return '';
    },
    setProperty(): void {},
    item(): string {
      return '';
    },
    get length(): number {
      return Object.keys(style).length;
    },
    cssText: '',
    // Index signature for direct property access (e.g. style.display)
    [Symbol.toStringTag]: 'CSSStyleDeclaration',
  } as unknown as CSSStyleDeclaration;
}

window.getComputedStyle = () => createStyleStub();

// rc-resize-observer (used by rc-table / rc-textarea) needs ResizeObserver
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as Record<string, unknown>).ResizeObserver = ResizeObserverStub;
