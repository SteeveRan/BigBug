import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import { App as AntdApp } from 'antd';
import { store } from './store';
import App from './App';
import './colors.css';

/**
 * @file main.tsx
 * @description Точка входа фронтенда. Монтирует React-приложение в #root.
 *              ConfigProvider теперь внутри ThemeProvider (в App.tsx),
 *              поэтому здесь остаётся только AntdApp для message/notification API.
 * @dependencies react, react-redux, antd, ./store, ./App
 * @relatedFiles App.tsx, colors.css, store/index.ts
 */

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');

createRoot(root).render(
  <StrictMode>
    <Provider store={store}>
      <AntdApp>
        <App />
      </AntdApp>
    </Provider>
  </StrictMode>
);
