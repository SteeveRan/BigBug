import { BrowserRouter } from 'react-router';
import { ThemeProvider } from './contexts/ThemeContext';
import { AppRouter } from './router';

/**
 * @file App.tsx
 * @description Корневой компонент приложения.
 *              Оборачивает роутер в ThemeProvider (переключение тёмная/светлая тема).
 * @dependencies react-router, ./contexts/ThemeContext, ./router
 * @relatedFiles main.tsx, contexts/ThemeContext.tsx
 */

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </ThemeProvider>
  );
}
