import { useState, useCallback, useMemo, useEffect } from 'react';
import type { ReactNode } from 'react';
import { ConfigProvider } from 'antd';
import { darkTheme, lightTheme } from '../theme';
import { ThemeContext, type ThemeMode, type ThemeContextValue } from './themeTypes';

/**
 * @file ThemeContext.tsx
 * @description Провайдер для переключения тёмной/светлой темы.
 *              Сохраняет выбор в localStorage, по умолчанию — тёмная тема.
 *              Применяет CSS data-атрибут `data-theme` на <html> для CSS-переменных.
 *              Типы и контекст вынесены в themeTypes.ts для react-refresh
 *              (only-export-components).
 * @dependencies antd ConfigProvider, ../theme.ts, ./themeTypes.ts
 * @relatedFiles ./themeTypes.ts, ../hooks/useThemeMode.ts, ../theme.ts, ../colors.css
 */

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

