# Frontend Development Guide

Руководство по разработке frontend части BigBug на React + TypeScript.

## Технологический стек

- **React 19** + **TypeScript**
- **Vite** - build tool с HMR
- **Yarn 4.3.1** - package manager
- **Redux Toolkit 2.3+** + **RTK Query** - state management и API клиент
- **Ant Design 6.4.3** - компонентная библиотека
- **React Router v7** - маршрутизация
- **keycloak-js 26+** - SSO адаптер
- **Vitest** + **@testing-library/react** - unit тесты
- **ESLint** + `@typescript-eslint` - линтинг

## Структура проекта

```
frontend/src/
├── components/        # Переиспользуемые UI-компоненты
├── hooks/             # Custom React hooks
├── pages/             # Страницы (один компонент = одна папка)
├── router/            # React Router конфигурация
├── services/          # Внешние сервисы (Keycloak)
├── store/             # Redux + RTK Query
├── tests/             # Vitest тесты
├── types/             # TypeScript интерфейсы
├── App.tsx            # Корневой компонент
├── main.tsx           # Точка входа
└── theme.ts           # Ant Design тема (ConfigProvider)
```

## Настройка окружения

### Установка зависимостей

```bash
# Убедиться что используется Node.js 26 LTS
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 26

cd frontend
yarn install
```

### Переменные окружения

Создать `frontend/.env.local`:

```bash
VITE_API_URL=http://localhost:8000
VITE_KEYCLOAK_URL=http://localhost:8180
VITE_KEYCLOAK_REALM=bigbug
VITE_KEYCLOAK_CLIENT_ID=bigbug-frontend
```

### Запуск для разработки

```bash
cd frontend

# Dev server с HMR
yarn dev

# Приложение доступно по адресу: http://localhost:5173
```

## Работа с типами

Все TypeScript интерфейсы централизованы в [`src/types/index.ts`](../../frontend/src/types/index.ts).

### Добавление нового типа

```typescript
// src/types/index.ts

// Статус флаги (унифицированные)
export type StatusFlag = 0 | 1 | 2 | 3 | 4;
// 0 = OK, 1 = Failed, 2 = Warning/Stale, 3 = In Progress, 4 = Pending

export interface Resource {
  id: number;
  name: string;
  description?: string;
  status_flag: StatusFlag;
  status_text: string;
  created_at: string;
  updated_at?: string;
}

export interface ResourceCreate {
  name: string;
  description?: string;
}

export interface ResourceUpdate {
  name?: string;
  description?: string;
}
```

## Работа с API (RTK Query)

Все API endpoints определены в [`src/store/api.ts`](../../frontend/src/store/api.ts).

### Добавление нового endpoint

```typescript
// src/store/api.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { Resource, ResourceCreate } from '../types';

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: import.meta.env.VITE_API_URL + '/api',
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.token;
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: ['Resource', 'Mirror', 'Image', 'HelmChart', 'DockerImage'],
  endpoints: (builder) => ({
    // Список ресурсов
    getResources: builder.query<Resource[], void>({
      query: () => '/resources',
      providesTags: ['Resource'],
    }),
    
    // Один ресурс
    getResource: builder.query<Resource, number>({
      query: (id) => `/resources/${id}`,
      providesTags: (result, error, id) => [{ type: 'Resource', id }],
    }),
    
    // Создать ресурс
    createResource: builder.mutation<Resource, ResourceCreate>({
      query: (data) => ({
        url: '/resources',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Resource'],
    }),
    
    // Удалить ресурс
    deleteResource: builder.mutation<void, number>({
      query: (id) => ({
        url: `/resources/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Resource'],
    }),
    
    // Кастомное действие
    syncResource: builder.mutation<void, number>({
      query: (id) => ({
        url: `/resources/${id}/sync`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, id) => [{ type: 'Resource', id }],
    }),
  }),
});

// Экспортировать хуки
export const {
  useGetResourcesQuery,
  useGetResourceQuery,
  useCreateResourceMutation,
  useDeleteResourceMutation,
  useSyncResourceMutation,
} = api;
```

### Использование в компоненте

```typescript
import { useGetResourcesQuery, useCreateResourceMutation } from '../../store/api';

function ResourceList() {
  const { data: resources, isLoading, error } = useGetResourcesQuery();
  const [createResource, { isLoading: isCreating }] = useCreateResourceMutation();
  
  const handleCreate = async (name: string) => {
    try {
      await createResource({ name }).unwrap();
      // Успех - RTK Query автоматически инвалидирует кеш
    } catch (err) {
      console.error('Failed to create resource:', err);
    }
  };
  
  const { message } = App.useApp();
  
  if (isLoading) return <Spin />;
  if (error) return <Alert type="error" message="Failed to load resources" />;
  
  return (
    <List
      dataSource={resources}
      renderItem={(resource) => (
        <List.Item>
          <List.Item.Meta title={resource.name} />
          <StatusChip status={resource.status_flag} />
        </List.Item>
      )}
    />
  );
}
```

## Создание новой страницы

### 1. Создать компонент страницы

```
frontend/src/pages/ResourceName/index.tsx
```

```typescript
// src/pages/ResourceName/index.tsx
import React from 'react';
import {
  Typography,
  Button,
  Table,
  Space,
  Spin,
  Alert,
  App,
} from 'antd';
import { useGetResourcesQuery, useDeleteResourceMutation } from '../../store/api';
import StatusChip from '../../components/StatusChip';

const ResourceNamePage: React.FC = () => {
  const { data: resources, isLoading, error } = useGetResourcesQuery();
  const [deleteResource] = useDeleteResourceMutation();
  const { message } = App.useApp();
  
  if (isLoading) {
    return <Spin />;
  }
  
  if (error) {
    return <Alert type="error" message="Failed to load data" />;
  }
  
  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: Resource) => (
        <StatusChip status={record.status_flag} label={record.status_text} />
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => new Date(val).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: Resource) => (
        <Button size="small" danger onClick={() => deleteResource(record.id)}>
          Delete
        </Button>
      ),
    },
  ];
  
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Resources</Typography.Title>
        <Button type="primary">Add Resource</Button>
      </div>
      
      <Table
        columns={columns}
        dataSource={resources}
        rowKey="id"
      />
    </div>
  );
};

export default ResourceNamePage;
```

### 2. Добавить маршрут

В [`src/router/index.tsx`](../../frontend/src/router/index.tsx):

```typescript
import ResourceNamePage from '../pages/ResourceName';

// В массиве маршрутов:
{
  path: '/resources',
  element: (
    <ProtectedRoute>
      <ResourceNamePage />
    </ProtectedRoute>
  ),
},
```

### 3. Добавить в навигацию

В [`src/components/Layout/index.tsx`](../../frontend/src/components/Layout/index.tsx):

```typescript
const navItems = [
  // ...existing items
  { label: 'Resources', path: '/resources', icon: <ResourceIcon /> },
];
```

## Аутентификация

### Keycloak SSO

Инициализация в [`src/services/keycloak.ts`](../../frontend/src/services/keycloak.ts):

```typescript
import Keycloak from 'keycloak-js';

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: import.meta.env.VITE_KEYCLOAK_REALM,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
});

export default keycloak;
```

Использование хука [`src/hooks/useKeycloakAuth.ts`](../../frontend/src/hooks/useKeycloakAuth.ts):

```typescript
import { useKeycloakAuth } from '../../hooks/useKeycloakAuth';

function MyComponent() {
  const { isAuthenticated, user, logout } = useKeycloakAuth();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  return <div>Welcome, {user?.email}</div>;
}
```

### Auth State (Redux)

В [`src/store/authSlice.ts`](../../frontend/src/store/authSlice.ts):

```typescript
import { useSelector } from 'react-redux';
import { RootState } from '../store';

// Получить текущего пользователя
const user = useSelector((state: RootState) => state.auth.user);
const token = useSelector((state: RootState) => state.auth.token);
const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated);
```

## Компоненты

### StatusChip

Унифицированный компонент для отображения статуса:

```typescript
import StatusChip from '../../components/StatusChip';

// Использование
<StatusChip status={0} />           // OK (зелёный)
<StatusChip status={1} />           // Failed (красный)
<StatusChip status={2} />           // Warning/Stale (жёлтый)
<StatusChip status={3} />           // In Progress (синий)
<StatusChip status={4} />           // Pending (серый)
<StatusChip status={0} label="Synced" />  // Кастомный текст
```

### Layout

Основной layout с навигацией:

```typescript
import Layout from '../../components/Layout';

// Используется автоматически через router
// Все защищённые страницы оборачиваются в Layout
```

## Тестирование

### Запуск тестов

```bash
cd frontend

# Все тесты (unit + integrations)
./scripts/test.sh

# Только unit
./scripts/test.sh --unit

# Только integrations
./scripts/test.sh --integrations

# С покрытием
./scripts/test.sh --coverage

# Отладка конкретного теста
./scripts/test.sh -f DockerImages -t "should render"

# Watch mode (для разработки)
yarn test
```

### Пример теста компонента

```typescript
// src/tests/integrations/ResourceList.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { store } from '../store';
import ResourceNamePage from '../pages/ResourceName';

// Mock RTK Query
vi.mock('../store/api', () => ({
  useGetResourcesQuery: () => ({
    data: [
      { id: 1, name: 'Test Resource', status_flag: 0, status_text: 'OK', created_at: '2024-01-01' }
    ],
    isLoading: false,
    error: null,
  }),
  useDeleteResourceMutation: () => [vi.fn(), { isLoading: false }],
}));

describe('ResourceNamePage', () => {
  it('renders resource list', async () => {
    render(
      <Provider store={store}>
        <ResourceNamePage />
      </Provider>
    );
    
    await waitFor(() => {
      expect(screen.getByText('Test Resource')).toBeInTheDocument();
    });
  });
  
  it('shows loading state', () => {
    vi.mocked(useGetResourcesQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    
    render(
      <Provider store={store}>
        <ResourceNamePage />
      </Provider>
    );
    
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
```

## Качество кода

### Линтинг и форматирование

```bash
cd frontend

# Prettier - форматирование
yarn format

# ESLint - линтинг
yarn lint

# TypeScript проверка типов (без компиляции)
npx tsc --noEmit

# Полная проверка
yarn format && yarn lint && npx tsc --noEmit && ./scripts/test.sh
```

### Конфигурация ESLint

В [`eslint.config.js`](../../frontend/eslint.config.js) настроены правила для TypeScript и React.

## Сборка для production

```bash
cd frontend

# Сборка
yarn build

# Предпросмотр production сборки
yarn preview
```

Артефакты сборки в `frontend/dist/`.

## Troubleshooting

### Ошибки типов

```bash
# Очистить кеш и переустановить
rm -rf node_modules/.vite
yarn install

# Проверить типы
npx tsc --noEmit
```

### API не подключается

```bash
# Проверить backend
curl http://localhost:8000/api/health

# Проверить VITE_API_URL в .env.local
cat frontend/.env.local
```

### Keycloak SSO не работает

```bash
# Проверить Keycloak
curl http://localhost:8180/realms/bigbug

# Проверить конфигурацию SSO в backend
curl http://localhost:8000/api/auth/sso/config
```

### Yarn ошибки

```bash
# Пересоздать lock file
rm yarn.lock && yarn install

# Очистить кеш Yarn
yarn cache clean
```

## Best Practices

- **Страницы**: папка с `index.tsx` в `src/pages/ComponentName/`
- **Компоненты**: переиспользуемые в `src/components/`
- **Типы**: централизованы в `src/types/index.ts`
- **API**: все endpoints в `src/store/api.ts` через RTK Query
- **Маршрутизация**: в `src/router/index.tsx`
- **Не использовать `any`**: всегда типизировать данные
- **Обработка ошибок**: всегда обрабатывать `isLoading` и `error` состояния
- **Компоненты**: функциональные с TypeScript интерфейсами для props

## Полезные ссылки

- [React 19 Documentation](https://react.dev/)
- [Redux Toolkit Documentation](https://redux-toolkit.js.org/)
- [RTK Query Documentation](https://redux-toolkit.js.org/rtk-query/overview)
- [Ant Design 6 Documentation](https://ant.design/)
- [React Router v7 Documentation](https://reactrouter.com/)
- [Vitest Documentation](https://vitest.dev/)
- [`frontend/package.json`](../../frontend/package.json) - актуальные зависимости
- [`AGENTS.md`](../../AGENTS.md) - quick reference
