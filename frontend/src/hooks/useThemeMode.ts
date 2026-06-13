/**
 * @file useThemeMode.ts
 * @description Хук для получения текущего режима темы и функции переключения.
 * @dependencies ../contexts/ThemeContext
 * @relatedFiles ../contexts/ThemeContext.tsx, ../theme.ts
 */

import { useContext } from 'react';
import { ThemeContext, type ThemeContextValue } from '../contexts/themeTypes';

/**
 * Хук для получения текущего режима темы и функции переключения.
 *
 * @example
 * const { mode, toggleTheme } = useThemeMode();
 * // mode === 'dark' | 'light'
 * // toggleTheme() — переключает тему
 */
export function useThemeMode(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useThemeMode must be used within <ThemeProvider>');
  }
  return ctx;
}
