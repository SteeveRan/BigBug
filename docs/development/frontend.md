# Frontend Development Guide

Руководство по разработке frontend части BigBug на React + TypeScript.

## Технологический стек

Решения по стеку зафиксированы в [ADR-0002](../adr/frontend/0002-frontend-stack-react-antd-rtk.md) (React 19 + TypeScript + AntD 6 + Redux Toolkit/RTK Query + Vite) и [ADR-0015](../adr/frontend/0015-frontend-unit-testing-vitest.md) (тестирование). Актуальные версии — [`frontend/package.json`](../../frontend/package.json); источник истины — код и реестр [ADR](../adr/README.md).

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
# Убедиться что используется актуальная LTS-версия Node.js (см. ADR-0002; фактически в контейнере — node:20-alpine)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use --lts

cd frontend
yarn install
```

### Переменные окружения

Создать `frontend/.env.local`:

```bash
VITE_API_URL=http://localhost:8000
```

Единственная используемая frontend-переменная — `VITE_API_URL`. Конфигурация SSO приходит с backend'а (`GET /api/auth/sso/config`: url, realm, client_id — ADR-0003); frontend env-переменных для Keycloak не существует (см. также раздел «Аутентификация»).

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

API-слой построен по схеме **base + injectEndpoints**:

- [`src/store/api/base.ts`](../../frontend/src/store/api/base.ts) — единственный `createApi`: `baseQuery` (обёрнут в `customBaseQuery`, который при любом 401 диспатчит `logout()`) и полный список `tagTypes`;
- [`src/store/api/<domain>.ts`](../../frontend/src/store/api/) — файл на домен (`auth.ts`, `gold-images.ts`, `providers.ts`, `git-mirroring/`, ...), каждый добавляет свои endpoint'ы через `api.injectEndpoints(...)`;
- [`src/store/api.ts`](../../frontend/src/store/api.ts) — агрегатор: побочные импорты всех доменных файлов (регистрируют endpoint'ы) + реэкспорт всех сгенерированных хуков. Приложение импортирует хуки только из `store/api`.

### Добавление нового endpoint

```typescript
// src/store/api/resources.ts — новый доменный файл
import { api } from './base';
import type { Resource, ResourceCreate } from '../../types';

const extendedApi = api.injectEndpoints({
  endpoints: (builder) => ({
    getResources: builder.query<Resource[], void>({
      query: () => '/resources',
      providesTags: ['Resource'],
    }),
    createResource: builder.mutation<Resource, ResourceCreate>({
      query: (data) => ({ url: '/resources', method: 'POST', body: data }),
      invalidatesTags: ['Resource'],
    }),
  }),
});

export const { useGetResourcesQuery, useCreateResourceMutation } = extendedApi;
```

Затем зарегистрировать домен и реэкспортировать хуки в агрегаторе:

```typescript
// src/store/api.ts
import './api/resources';                       // регистрация endpoint'ов
export { useGetResourcesQuery, useCreateResourceMutation } from './api/resources';
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

В [`src/router/index.tsx`](../../frontend/src/router/index.tsx) — JSX-конфигурация с `createBrowserRouter`-деревом: маршруты объявляются элементами `<Route>`, защищённые — обёрнуты в `<ProtectedRoute>` и `<PermissionGate>` (по permission, ADR-0004):

```tsx
import ResourceNamePage from '../pages/ResourceName';

<Route
  path="resources"
  element={
    <ProtectedRoute>
      <PermissionGate permission="resources:read">
        <ResourceNamePage />
      </PermissionGate>
    </ProtectedRoute>
  }
/>
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

Keycloak-js как runtime-зависимость **не используется** (fitness-правило ADR-0003). SSO строится на PKCE-хелперах в [`src/services/keycloak.ts`](../../frontend/src/services/keycloak.ts) (`redirectToKeycloakLogin`, `SSO_VERIFIER_KEY`) — конфигурация приходит с backend'а через `GET /api/auth/sso/config`, а не из env-переменных.

Хук [`src/hooks/useKeycloakAuth.ts`](../../frontend/src/hooks/useKeycloakAuth.ts) — фактическая сигнатура:

```typescript
const { ready, enabled, config, error, login, handleCallback } = useKeycloakAuth();

// ready — конфиг получен и обработан
// enabled — backend сообщил, что SSO включён
// login() — старт PKCE-редиректа на Keycloak
// handleCallback() — на /sso/callback: извлекает code + code_verifier
//   для POST /api/auth/oidc/exchange ({ code, redirect_uri, code_verifier } | { error })
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
- **API**: base-слайс в `src/store/api/base.ts`, доменные файлы с `injectEndpoints` в `src/store/api/`, агрегатор `src/store/api.ts` — хуки импортируются только из него
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
