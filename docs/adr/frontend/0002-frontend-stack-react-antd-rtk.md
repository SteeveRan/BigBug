---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
---
# Выбрать frontend-стек: React 19 + TypeScript + Ant Design 6 + Redux Toolkit (RTK Query) + Vite

## Context and Problem Statement

Официальной фиксации реального стека нет.

Вопрос: какой frontend-стек закрепить как официальный для SPA BigBug?

## Decision Drivers

- Enterprise-UI с плотными таблицами, формами и настройками (Providers, RBAC, pipelines) — нужна зрелая компонентная библиотека с готовыми сложными виджетами (Table, Form, Tree, Select)
- TypeScript обязателен: весь код типизирован, `tsc --noEmit` в CI
- State management: кэширование REST-ответов `/api/*` с автоматической инвалидацией после мутаций
- SSO через Keycloak (OIDC) — нужен официальный адаптер
- Минимализм: ничего «для будущего», каждая зависимость уже используется кодом
- Расхождение «документация vs код» должно быть устранено в пользу кода

## Considered Options

- Vue 3 + Vuetify/Element Plus
- Angular
- Svelte (+ SvelteKit)
- React 19 + MUI (Material UI)
- React 19 + Ant Design 6 + Redux Toolkit (RTK Query) + react-router v7 + Vite
- State: React Query / TanStack Query vs RTK Query; Zustand vs Redux Toolkit

## Decision Outcome

Chosen option: **React 19 + Ant Design 6 + Redux Toolkit (RTK Query) + react-router v7 + Vite** — фактический стек проекта, проверенный по `frontend/package.json`. React выбран как индустриальный стандарт SPA; AntD 6 даёт наиболее полные enterprise-компоненты «из коробки» (Table с сортировкой/фильтрами, Form с валидацией, Tree, Transfer), что критично для админ-интерфейса DevOps-платформы; RTK Query покрывает и state, и серверный кэш одной зависимостью.

Конкретный стек (версии сверены с `frontend/package.json`, 2026-10-21):

- **TypeScript ^5.5**
- **react-dom ^19.0.0**
- **React ^19.0.0**
- **antd ^6.4.3** + **@ant-design/icons ^6.2.5** (+ `@ant-design/x-markdown`, `@uiw/react-markdown-preview` для markdown-рендеринга)
- State: **@reduxjs/toolkit ^2.3.0** (включая **RTK Query**) + **react-redux ^9.1.0**
- Роутинг: **react-router ^7.0.0** (не `react-router-dom`)
- Auth: **keycloak-js ^26.2.4** (OIDC/Keycloak SSO)
- HTTP: **axios ^1.7.0** (базовый клиент; данные — через RTK Query)
- Сборка: **Vite ^5.4.0** + `@vitejs/plugin-react`
- Качество: **Vitest ^2.0.0** + `@testing-library/react` + `jsdom` (unit + integrations), **ESLint 9** + `typescript-eslint 8`, **Prettier**, **knip** (dead code)
- **Runtime: Node.js 26 LTS**
- Пакетный менеджер: **Yarn 4.3.1** (`packageManager` в `package.json`)

### Consequences

- Good, because AntD 6 покрывает 90% enterprise-UI готовыми компонентами — меньше собственного UI-кода
- Good, because RTK Query даёт кэш + инвалидацию по тегам без отдельной библиотеки (React Query не нужен)
- Bad, because AntD тянет тяжёлый бандл — нужен контроль через tree-shaking и lazy-роуты
- Bad, because `plans/architecture/decisions.md` устарел (MUI v9, Node 26) — исправляется владельцами этих документов, не этим ADR
- Neutral, because react-router v7 вместо react-router-dom — новый канонический пакет, часть туториалов в сети всё ещё ссылается на старый

### Confirmation

Версии в Decision Outcome сверяются с `frontend/package.json` — на 2026-10-21 сверены, расхождений нет. Fitness-критерий: `frontend/package.json` не должен содержать production-зависимостей, не упомянутых здесь (кроме транзитивных), и vice versa; появление второго UI-кита (MUI и т.п.) или второго data-fetching-слоя (React Query) — нарушение. Проверка dead-code: `make dead-code` (knip) не должен находить неиспользуемые зависимости из списка. Правило на будущее: новая frontend-зависимость или смена мажорной версии — триггер «новая зависимость» из `docs/adr/README.md`, требует обновления/нового ADR.

## Pros and Cons of the Options

### Vue 3 + Vuetify/Element Plus

- Good, because меньший порог входа, реактивность из коробки
- Bad, because экосистема enterprise-компонентов и найм — уже, чем у React; миграция существующего кода бессмысленна

### Angular

- Good, because batteries included: DI, роутинг, формы, RxJS
- Bad, because избыточная сложность и opinionated-структура для SPA одного продукта; несовместим с существующим кодом

### Svelte (+ SvelteKit)

- Good, because минимальный рантайм, меньше boilerplate
- Bad, because недостаточная зрелость enterprise-экосистемы (компонентные киты, инструменты) для платформы с RBAC и плотными таблицами

### React 19 + MUI (Material UI)

- Good, because React-совместимо; зрелая библиотека
- Bad, because фактически не используется в коде — выбор MUI означал бы переписывание всего UI; AntD богатее для data-heavy enterprise-интерфейсов (Table/Form из коробки)

### React 19 + Ant Design 6 + RTK Query + Vite — chosen

- Good, because это уже работающий код; ADR фиксирует статус-кво, а не миграцию
- Good, because AntD Table/Form/Tree закрывают основные экраны (mirrors, providers, pipelines, RBAC) без кастомных компонентов
- Bad, because тяжёлый бандл AntD; кастомный дизайн поверх AntD ограничен его дизайн-системой

### State: React Query / TanStack Query vs RTK Query

- Good (React Query), because лучший DX для чисто серверного кэша
- Bad, because вторая библиотека поверх Redux; RTK Query уже входит в @reduxjs/toolkit и даёт нормализованный клиентский state (auth, UI-state) в одном месте

### State: Zustand vs Redux Toolkit

- Good (Zustand), because минимальный boilerplate
- Bad, because нет встроенного серверного кэша и DevTools-экосистемы; для сложного state (permissions, providers, pipelines) RTK-структура предсказуемее

## More Information

- Первичные рассуждения — `plans/architecture/decisions.md` (раздел «Frontend: React 19 + TypeScript»; **устарел**: там MUI v9, источник истины — `frontend/package.json`)
- `plans/tech-stack.md` удалён [ADR-0013](../infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md); расхождение по MUI/Node зафиксировано как устаревший факт ADR-0002
- Конвенции реализации — `plans/development/frontend.md`; тестовые решения — семейство ADR-0014…0018 (реестр: [docs/adr/README.md](../README.md))
- Парный ADR: [ADR-0001](../backend/0001-choose-backend-stack.md) (backend-стек)
- Условие пересмотра: смена UI-кита или появление второго data-fetching-слоя — только через новый ADR