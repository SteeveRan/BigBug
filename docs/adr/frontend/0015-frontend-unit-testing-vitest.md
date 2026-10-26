---
status: accepted
date: 2026-10-21
decision-makers: SteeveRan
---

# Зафиксировать frontend unit-тестирование: Vitest + @testing-library/react + jsdom, layout `src/tests/unit/`

## Context and Problem Statement

Стек зафиксирован в [ADR-0002](0002-frontend-stack-react-antd-rtk.md) (Vitest упомянут в списке «Качество»), но решения по unit-тестированию фронтенда — выбор раннера, DOM-окружение, layout тестовых файлов, конвенции мокирования — нигде формально не зафиксированы. Единственный документ — `docs/development/testing.md`, который разделяется пятью тестовыми доменами (backend unit / frontend unit / backend integrations / frontend integrations / e2e) и будет удалён после выхода всех пяти ADR (последним — ADR-0018, e2e). Внутри него пример конфигурации Vitest уже разошёлся с кодом (`setup.ts` вместо фактического `setup.tsx`, неполный список coverage-репортеров).

Фактический вопрос: **принять ли существующий Vitest-стек и layout `src/tests/unit/` как стандарт unit-тестирования фронтенда** и зафиксировать его в ADR?

Фактическое состояние (проверено по коду, 2026-10-21):

- Раннер — **Vitest ^2.0.0** (пакеты `vitest`, `@vitest/coverage-v8`, `@vitest/ui` в `frontend/package.json`); конфиг — отдельный `frontend/vitest.config.ts` (не внутри `vite.config.ts`)
- Окружение — **jsdom ^25.0.0**, `globals: true`; setup-файл — `./src/tests/integrations/setup.tsx` (общий для unit и integrations: `@testing-library/jest-dom`, полифиллы `window.matchMedia`, моки `ThemeContext`/`useThemeMode` для antd)
- Утилиты — `@testing-library/react ^16`, `@testing-library/jest-dom ^6.4`, `@testing-library/user-event ^14.5`, `@testing-library/dom ^10.4`
- Coverage — provider `v8`, репортеры `text, text-summary, json, json-summary, html, lcov`, каталог `./coverage`, включено `src/**/*.{ts,tsx}` (исключены `src/tests/**`, `src/main.tsx`, `src/vite-env.d.ts`), thresholds — все 0
- Layout — `frontend/src/tests/unit/*.test.ts(x)`: `authSlice.test.ts`, `keycloak.service.test.ts`, `providersColumns.test.ts`, `providersStore.test.ts`, `splitMyProviders.test.ts`, `teamsStore.test.ts`, `useKeycloakAuth.test.tsx` (50 тестов)
- Запуск — `frontend/scripts/test.sh --unit` (фильтры `-f <файл>`, `-t <имя теста>`, coverage, watch, UI), Make-цель `make test-unit-frontend` с пробросом `TEST_ARGS`
- Типы unit-тестов в коде: чистые редьюсеры (authSlice, providersStore, teamsStore), pure-функции (splitMyProviders, resolveProviderColumns), сервисы с `vi.mock` API-слоя (keycloak.service), хуки через `renderHook` (useKeycloakAuth)

## Decision Drivers

- Vite-native сборка: конфиг Vitest переиспользует плагин `@vitejs/plugin-react` и alias `@` → `/src` из `vite.config.ts` без дублирования — Jest потребовал бы отдельной трансформации (babel/ts-jest) и синхронизации alias'ов
- Jest-совместимый API Vitest (`describe`/`it`/`expect`/`vi`) — существующие 7 файлов unit-тестов миграции не требуют
- Enterprise-UI на antd: даже изолированные хуки (useKeycloakAuth) рендерятся в DOM — нужен эмулятор браузера в unit-прогоне
- Тесты изолированы от сети и store: RTK Query-хуки и keycloak-сервис мокаются через `vi.mock`, unit-тесты не поднимают Redux Provider и не ходят в `/api/*`
- Минимализм (унаследован из ADR-0002): фиксация работающего статус-кво, а не миграция

## Considered Options

* Vitest ^2 + @testing-library/react + jsdom — фактический стандарт кода
* Jest 29 + @testing-library/react + jsdom
* Cypress Component Testing
* Playwright Component Testing (experimental)

## Decision Outcome

Chosen option: **Vitest ^2.0.0 + @testing-library/react ^16 + jsdom ^25** — фактический стандарт кода (7 файлов, 50 тестов в `src/tests/unit/`), полностью совместим с фиксацией Vitest в ADR-0002 и не требует ни одной строки миграции.

### Зафиксированные правила

**1. Конфигурация** (`frontend/vitest.config.ts` — эталон; source of truth — файл, а не примеры в docs):

- отдельный `vitest.config.ts` (не секция `test` внутри `vite.config.ts`), с тем же плагином `@vitejs/plugin-react` и alias `'@' → '/src'`, что и в `vite.config.ts`
- `test.globals: true` — `describe`/`it`/`expect` без импорта; в существующих тестах импорт из `vitest` сохраняется (допустимы оба стиля, явный импорт — предпочтительный)
- `test.environment: 'jsdom'` — DOM-эмулятор для всех тестов, включая unit (для чистых функций DOM не нужен, но и не мешает)
- `test.setupFiles: ['./src/tests/integrations/setup.tsx']` — общий setup для unit и integrations (`@testing-library/jest-dom`, полифиллы antd)

**2. Layout**:

| Тип | Каталог | Суффикс | Что тестируется |
|---|---|---|---|
| Unit | `frontend/src/tests/unit/` | `*.test.ts` / `*.test.tsx` | редьюсеры, pure-функции, сервисы с `vi.mock`, хуки через `renderHook` |

- Имя файла = имя тестируемого модуля: `authSlice.test.ts` для `src/store/authSlice.ts`, `keycloak.service.test.ts` для `src/services/keycloak.ts`
- `.tsx` — только когда тест рендерит JSX (обёртки для `renderHook`)
- Тесты НЕ colocate рядом с исходниками: всё — под `src/tests/` (unit / integrations / e2e)

**3. Конвенции unit-тестов**:

- Изоляция от сети и глобального state: RTK Query-хуки мокаются через `vi.mock('../../store/api', ...)`, keycloak-адаптер — через моки `keycloak-js`; unit-тест не поднимает реальный Redux `Provider` (это — зона integrations, ADR-0017)
- Пользовательские действия в hook-тестах — через `@testing-library/user-event` / `waitFor`, не через прямые вызовы внутренних функций компонента
- Ассерты DOM — матчеры `@testing-library/jest-dom` (`toBeInTheDocument` и т.п.)
- Coverage thresholds в конфиге — 0 (осознанно: покрытие не является gate; контроль качества — линт, типы, ручной рост покрытия)

**4. Запуск**:

```bash
make test-unit-frontend                                  # все unit
make test-unit-frontend TEST_ARGS="-f authSlice"         # по части имени файла
make test-unit-frontend TEST_ARGS="-t 'should return'"   # по имени теста
make coverage-all                                        # coverage обоих стеков
```

Напрямую — `./frontend/scripts/test.sh --unit [-c] [-f <name>] [-t <pattern>] [-w] [--ui]`. Watch/UI-режимы (`yarn test`, `yarn test:ui`) — для локальной разработки, не для CI.

### Consequences

* Good, because ноль миграций: 7 существующих unit-файлов уже соответствуют правилам
* Good, because Vite-native: один alias/плагин-конфиг на dev-сборку и тесты; скорость запуска выше, чем у Jest с ts-jest/babel
* Good, because Jest-совместимый API — документация и примеры из экосистемы React Testing Library применимы напрямую
* Bad, because setup-файл общий с integrations и тянет в unit-прогон моки antd (ThemeContext, matchMedia) — лишнее для чистых редьюсеров; разъединение setup'ов возможно позже без смены раннера
* Bad, because jsdom — не реальный браузер: отсутствуют layout, реальные события фокуса/скролла; ограничения компенсируются e2e-уровнем (ADR-0018)
* Neutral, because coverage thresholds 0 — покрытие мониторится вручную через `make coverage-all`, gate не вводится до стабилизации кодовой базы
* Non-goals: Cypress/Playwright component testing (unit-уровень уже закрыт), screenshot-тестирование, перевод `globals` на false, изменение структуры `src/tests/`

### Confirmation

1. **Прогон unit-набора** (все правила layout'а и изоляции проверяются компиляцией и падением при мутации):

```bash
make test-unit-frontend
```

Ожидаемый результат: 7 файлов, 50 тестов, 0 failed.

2. **Раннер и окружение не подменяются** — при ревью: `frontend/package.json` не содержит `jest` (ни в dependencies, ни в scripts), `vitest.config.ts` сохраняет `environment: 'jsdom'` и setup-файл. Быстрая проверка:

```bash
# ожидание: пусто
grep -n '"jest' frontend/package.json
```

3. **Layout** — при ревью: новые unit-тесты только в `frontend/src/tests/unit/` с суффиксом `.test.ts(x)`; knip (`make dead-code`) не находит тестовых файлов вне `src/tests/`.

## Pros and Cons of the Options

### Vitest ^2 + @testing-library/react + jsdom — chosen

Фактический стандарт кода.

* Good, because Vite-native: единая трансформация TS/TSX и alias'ов с продовой сборкой, без babel-конфига
* Good, because Jest-совместимый API (`vi.fn`, `vi.mock`, матчеры) — миграция с/на Jest механическая
* Good, because первый-class поддержка coverage через `@vitest/coverage-v8` без дополнительных плагинов
* Bad, because мажорные релизы Vitest чаще, чем у Jest; апгрейды требуют внимания (v2 → v3 ломающих изменений немного, но есть)

### Jest 29 + @testing-library/react + jsdom

Индустриальный дефолт вне Vite-проектов.

* Good, because максимальная зрелость и экосистема снапшот-моков
* Bad, because требует отдельной трансформации TSX (babel или ts-jest) и ручной синхронизации alias `@` с `vite.config.ts` — два источника истины для сборки
* Bad, because переписывание импортов и настройки во всех существующих тестах ради нуля функциональной выгоды

### Cypress Component Testing

Браузерный раннер компонент в изоляции.

* Good, because рендер в реальном браузере: видимость layout, реальные события
* Bad, because медленный старт и тяжёлый рантайм для 50 изолированных тестов; дублирует e2e-инфраструктуру Cypress (ADR-0018) на unit-уровне
* Bad, because не используется в коде — означало бы миграцию всех unit-тестов

### Playwright Component Testing (experimental)

Аналог Cypress CT на Playwright.

* Good, because реальный браузер + зрелый e2e-раннер
* Bad, because component testing остаётся experimental; риски API-стабильности выше, чем ценность для изолированных unit-тестов

## More Information

- Родственные ADR: [ADR-0002](0002-frontend-stack-react-antd-rtk.md) (frontend-стек: Vite, Vitest в списке «Качество»), [ADR-0014](../backend/0014-backend-unit-testing-pytest.md) (backend unit — парный, семейство тестовых ADR), ADR-0016/0017 (integrations, запланированы), ADR-0018 (e2e, запланирован)
- Реестр ADR и конвенции: [docs/adr/README.md](../README.md)
- Источник истины по конфигурации: `frontend/vitest.config.ts`, `frontend/package.json`, `frontend/scripts/test.sh`, `frontend/src/tests/integrations/setup.tsx`
- Условие пересмотра: мажорный апгрейд Vitest с ломающими изменениями конфига, потребность в реальном браузерном окружении для unit-тестов, либо разъединение setup-файлов unit/integrations — переоткрыть через новый ADR
- Этот ADR фиксирует frontend-раздел `docs/development/testing.md`; сам документ удаляется ADR-0018 (последним из семейства), до тех пор remaining-разделы не каноничны в части, покрытой ADR 0014–0017
