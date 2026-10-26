---
status: accepted
date: 2026-10-21
decision-makers: SteeveRan
---

# Зафиксировать frontend integration-тестирование: страницы с реальным Redux store, RTK Query-хуки в моках, jsdom, layout `src/tests/integrations/`

## Context and Problem Statement

Стек зафиксирован в [ADR-0002](0002-frontend-stack-react-antd-rtk.md), unit-уровень — в [ADR-0015](0015-frontend-unit-testing-vitest.md): там прямо указано, что «unit-тест не поднимает реальный Redux `Provider` (это — зона integrations)». Но решения по integration-тестированию фронтенда — что именно интегрируется, как мокаются RTK Query-эндпоинты, как рендерятся страницы с routing и antd-контекстом — нигде формально не зафиксированы. Единственный документ — `plans/development/testing.md`, который разделяется пятью тестовыми доменами и будет удалён после выхода всех пяти ADR (последним — ADR-0018, e2e).

Фактический вопрос: **принять ли существующую стратегию integration-тестов — реальный Redux store + ручные `vi.mock` RTK Query-хуков (без MSW) + jsdom-рендер страниц через `Provider`/`Router`/antd `App` — как стандарт, и зафиксировать её в ADR?**

Фактическое состояние (проверено по коду, 2026-10-21):

- Layout — `frontend/src/tests/integrations/*.test.tsx`: десятки тестовых файлов (GitMirroringMirrors, NavigationMenu, Providers, Pipelines, Admin*, Layout и др.)
- Раннер/окружение — общий с unit: Vitest ^2, `vitest.config.ts` (`environment: 'jsdom'`, `globals: true`), общий setup-файл `./src/tests/integrations/setup.tsx` (polyfills `window.matchMedia`, `ResizeObserver`, `getComputedStyle` для antd/rc-*; моки `ThemeContext`/`useThemeMode`)
- Обёртка рендера — реальный `configureStore` с `[api.reducerPath]: api.reducer` и `api.middleware` + `<Provider store>` + `BrowserRouter` (или `MemoryRouter` для маршрутов с параметрами) + `<App>` из antd; хелперы `createTestStore()` / `renderPage()` объявляются локально в каждом файле
- Стратегия мокирования — **ручные `vi.mock('../../store/api', ...)`** через `vi.importActual` + `vi.fn()` на каждый используемый хук (query: `{ data, isLoading, isError }`; mutation: `[triggerFn, { isLoading: false }]`); MSW в проекте не установлен
- `usePermissions` мокается отдельно (`vi.mock('../../hooks/usePermissions')`); в NavigationMenu — точные permission-строки с реальной проверкой вхождения, не `() => true`
- Сеть — не используется: хуки замоканы до вызова middleware, реальных HTTP-запросов нет
- Запуск — `frontend/scripts/test.sh --integrations` (фильтры `-f`, `-t`), Make-цель `make test-integrations-frontend` с пробросом `TEST_ARGS`

## Decision Drivers

- Страницы — тонкая прослойка над RTK Query: ценность интеграционного теста в проверке связки «store + компонент + контексты (router, antd App, permissions)», а не логики страницы в изоляции
- Реальный `api.reducer` + `api.middleware` в store: тесты видят кэширование/подписки RTK Query, а не только «что вернул хук» — при этом сеть полностью отсечена моками хуков
- MSW не нужен: перехват на сетевом уровне избыточен, когда мокается сам слой хуков — меньше зависимостей и настроек
- Enterprise-UI на antd: компонентам нужны `App`-контекст, breakpoints (`matchMedia`), таблицы (`ResizeObserver`) — покрыто общим setup-файлом
- Минимализм (унаследован из ADR-0002): фиксация работающего статус-кво, а не миграция

## Considered Options

* Vitest + jsdom + реальный Redux store + ручные `vi.mock` RTK Query-хуков — фактический стандарт кода
* Vitest + jsdom + MSW (перехват HTTP вместо мока хуков)
* Playwright Component Testing (браузерный рантайм)
* Storybook Interaction Tests (play-функции)

## Decision Outcome

Chosen option: **Vitest + jsdom + реальный Redux store + ручные `vi.mock` RTK Query-хуков** — фактический стандарт кода (все integration-тесты в `src/tests/integrations/`), ноль миграций, минимальная зависимость.

### Зафиксированные правила

**1. Что интегрируется, что мокается**:

| Компонент | Статус в integration-тесте |
|---|---|
| Redux store (`configureStore` + `api.reducer` + `api.middleware`) | реальный, создаётся заново на тест/файл |
| RTK Query-хуки (`useGetXQuery` / `useXMutation`) | `vi.mock('../../store/api')` + `vi.importActual`, каждый хук — `vi.fn()` |
| Сеть / HTTP | никогда не используется |
| Router (`BrowserRouter` / `MemoryRouter`) | реальный; `MemoryRouter` — для маршрутов с параметрами |
| antd (`<App>`, таблицы, модалки) | реальный, с polyfills из setup.tsx |
| `usePermissions` | мок (`vi.mock`); для permission-матриц — реальные строки + проверка вхождения |
| `ThemeContext` / `useThemeMode` | мок в общем setup.tsx |

**2. Типовые моки хуков** (хелперы `mockQuery`/`mockMutation` в каждом файле):

- query: `{ data: [...], isLoading: false, isError: false, error: null }`
- mutation: `[vi.fn().mockResolvedValue({ data: {} }), { isLoading: false }]`
- состояния загрузки/ошибки задаются в конкретном тесте переопределением `isLoading`/`isError`

**3. Layout**:

| Тип | Каталог | Суффикс | Что тестируется |
|---|---|---|---|
| Integration | `frontend/src/tests/integrations/` | `*.test.tsx` | страницы/компоненты с Redux store, RTK Query-моками, router и antd-контекстом |

- Имя файла = имя тестируемой страницы/компонента: `GitMirroringMirrors.test.tsx` для `src/pages/GitMirroring/Mirrors/`
- Общие polyfills и context-моки — в `src/tests/integrations/setup.tsx` (общий с unit, см. ADR-0015); `createTestStore()`/`renderPage()` — локальные хелперы внутри каждого тестового файла, без общего файла-обёртки

**4. Запуск**:

```bash
make test-integrations-frontend                                  # все integrations
make test-integrations-frontend TEST_ARGS="-f GitMirroringMirrors"  # по имени файла
make test-integrations-frontend TEST_ARGS="-t 'should render'"   # по имени теста
```

Напрямую — `./frontend/scripts/test.sh --integrations [-c] [-f <name>] [-t <pattern>]`.

### Consequences

* Good, because ноль миграций: 37 существующих файлов уже соответствуют правилам
* Good, because реальный store проверяет фактическую связку редьюсеров/middleware с компонентом — тест ловит рассинхрон селекторов и API-типов, недоступный unit-тестам
* Good, because мок хуков вместо перехвата сети (MSW) — проще: типы ответов выводятся из TS-схем напрямую, без описания HTTP-контрактов и серверных хендлеров
* Bad, because мок хука не проверяет сам RTK Query-эндпоинт (URL, method, tag invalidation) — контракт API остаётся непроверенным на этом уровне и покрывается backend-тестами (ADR-0014) и будущим e2e (ADR-0018)
* Bad, because при добавлении нового эндпоинта в `store/api.ts` моки в затронутых тестах нужно дописывать вручную (NavigationMenu уже несёт полный список хуков)
* Bad, because jsdom — не реальный браузер: нет layout и настоящих событий; компенсируется e2e-уровнем (ADR-0018)
* Neutral, because `createTestStore()` дублируется в каждом файле — сознательно: локальный хелпер проще общего `test-utils.ts` и не создаёт скрытой связности
* Non-goals: MSW, Playwright/Storybook component testing, screenshot-тесты, общий `test-utils`-модуль, покрытие HTTP-контрактов RTK Query

### Confirmation

1. **Прогон integration-набора**:

```bash
make test-integrations-frontend
```

Ожидаемый результат: все integration-тесты, 0 failed.

2. **Стратегия мокирования не подменяется** — при ревью: `frontend/package.json` не содержит `msw`; тесты не содержат реальных `fetch`/`httpx`-запросов. Быстрая проверка:

```bash
# ожидание: пусто
grep -n '"msw' frontend/package.json
```

3. **Layout** — при ревью: новые integration-тесты только в `frontend/src/tests/integrations/` с суффиксом `.test.tsx`, каждая страница — свой файл; рендер через `Provider` + router + `<App>`.

## Pros and Cons of the Options

### Vitest + jsdom + реальный store + `vi.mock` RTK Query-хуков — chosen

Фактический стандарт кода.

* Good, because проверяется связка store ↔ компонент ↔ контексты, а не изолированная логика
* Good, потому что мок на уровне хуков типобезопасен: форма ответа выводится из TS-типов `store/api.ts`
* Good, because ноль новых зависимостей
* Bad, because HTTP-контракт RTK Query (URL, теги кэша) не тестируется
* Bad, because ручная поддержка списка замоканных хуков

### Vitest + jsdom + MSW

Перехват HTTP-запросов на уровне `fetch` вместо мока хуков.

* Good, because тестируется полный путь хука → эндпоинт → ответ, включая URL и сериализацию
* Bad, because дублирование HTTP-контракта в хендлерах MSW: рассинхрон с `store/api.ts` ловится тестом, а не компилятором
* Bad, because миграция всех integration-тестов ради нуля функциональной выгоды для текущих сценариев

### Playwright Component Testing

Браузерный рантайм для компонентов в изоляции.

* Good, because реальный браузер: layout, настоящие события
* Bad, because тяжёлый старт для полного integration-набора; дублирует e2e-инфраструктуру (ADR-0018)
* Bad, because не используется в коде — означало бы миграцию всех integration-тестов

### Storybook Interaction Tests

Сценарии взаимодействия в Storybook (play-функции).

* Good, because визуальная документация состояний компонента «бесплатно»
* Bad, because требует введения Storybook в проект (отсутствует) и поддержки stories для каждой страницы — затраты не окупаются при уже написанных 37 тестовых файлах

## More Information

- Родственные ADR: [ADR-0002](0002-frontend-stack-react-antd-rtk.md) (frontend-стек), [ADR-0015](0015-frontend-unit-testing-vitest.md) (frontend unit — граница unit/integration: unit не поднимает Redux `Provider`, integration — поднимает), [ADR-0014](../backend/0014-backend-unit-testing-pytest.md) (backend unit), ADR-0016 (backend integrations, запланирован), ADR-0018 (e2e, запланирован — закрывает ограничения jsdom)
- Реестр ADR и конвенции: [docs/adr/README.md](../README.md)
- Источник истины: `frontend/src/tests/integrations/`, `frontend/vitest.config.ts`, `frontend/scripts/test.sh`, `frontend/package.json`
- Условие пересмотра: потребность в тестировании HTTP-контракта RTK Query на фронте (ввести MSW новым ADR), нестабильность моков хуков при росте числа эндпоинтов, либо мажорные ломающие изменения Vitest/RTL — переоткрыть через новый ADR
- Этот ADR фиксирует frontend-раздел `plans/development/testing.md`; сам документ удаляется ADR-0018 (последним из семейства), до тех пор remaining-разделы не каноничны в части, покрытой ADR 0014–0017
