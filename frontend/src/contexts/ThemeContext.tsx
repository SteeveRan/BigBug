import { createContext, useContext, useState, useCallback, useMemo, useEffect } from 'react';
import type { ReactNode } from 'react';
import { ConfigProvider } from 'antd';
import { darkTheme, lightTheme } from '../theme';

/**
 * @file ThemeContext.tsx
 * @description Контекст и провайдер для переключения тёмной/светлой темы.
 *              Сохраняет выбор в localStorage, по умолчанию — тёмная тема.
 *              Применяет CSS data-атрибут `data-theme` на <html> для CSS-переменных.
 * @dependencies antd ConfigProvider, ../theme.ts
 * @relatedFiles ../theme.ts, ../colors.css
 */

type ThemeMode = 'dark' | 'light';

interface ThemeContextValue {
  mode: ThemeMode;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = 'bigbug-theme';

function getInitialTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
  } catch {
    // localStorage недоступен (SSR, приватный режим)
  }
  return 'dark';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(getInitialTheme);

  const toggleTheme = useCallback(() => {
    setMode((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  // Синхронизируем data-theme атрибут и localStorage
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode);
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // noop
    }
  }, [mode]);

  const value = useMemo<ThemeContextValue>(() => ({ mode, toggleTheme }), [mode, toggleTheme]);

  const currentAntdTheme = mode === 'dark' ? darkTheme : lightTheme;

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider theme={currentAntdTheme}>{children}</ConfigProvider>
    </ThemeContext.Provider>
  );
}

/**
 * Хук для получения текущего режима темы и функции переключения.
 *
 * @example
 * const { mode, toggleTheme } = useThemeMode();
 * // mode === 'dark' | 'light'
 * // toggleTheme() — переключает тему
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useThemeMode(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useThemeMode must be used within <ThemeProvider>');
  }
  return ctx;
}
