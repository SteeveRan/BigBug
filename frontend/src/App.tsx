import { BrowserRouter } from 'react-router';
import { ThemeProvider } from './contexts/ThemeContext';
import { AppRouter } from './router';
import { MaintenanceBanner } from './components/MaintenanceBanner';

/**
 * @file App.tsx
 * @description Корневой компонент приложения.
 *              Оборачивает роутер в ThemeProvider (переключение тёмная/светлая тема).
 *              MaintenanceBanner смонтирован над роутером — виден на всех страницах,
 *              включая /login и /admin (они не шарят общий layout).
 * @dependencies react-router, ./contexts/ThemeContext, ./router, ./components/MaintenanceBanner
 * @relatedFiles main.tsx, contexts/ThemeContext.tsx, components/MaintenanceBanner/index.tsx
 */

export default function App() {
  return (
    <ThemeProvider>
      <MaintenanceBanner />
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </ThemeProvider>
  );
}
