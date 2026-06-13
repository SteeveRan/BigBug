/**
 * @file themeTypes.ts
 * @description Типы и контекст темы. Вынесены отдельно для соответствия
 *              react-refresh/only-export-components.
 * @relatedFiles ./ThemeContext.tsx, ../hooks/useThemeMode.ts, ../theme.ts
 */

import { createContext } from 'react';

export type ThemeMode = 'dark' | 'light';

export interface ThemeContextValue {
  mode: ThemeMode;
  toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);
