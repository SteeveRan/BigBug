---
status: proposed
date: 2026-10-26
decision-makers: "SteeveRan"
---

# UI-контракты: AntD-тема в коде — канон, Penpot — зеркальная библиотека и стенд эскизов

## Context and Problem Statement

Frontend BigBug построен на Ant Design 6 (ADR-0002) с брендированной темой:
`frontend/src/theme.ts` (AntD `ThemeConfig` — dark/light algorithm + brand-палитра
#7C3AED, радиусы, Inter) и `frontend/src/colors.css` (CSS-переменные `--bigbug-*`
для кастомных компонентов вне AntD).

UI-код пишут AI-агенты (opencode), которые склонны изобретать собственные цвета,
отступы и компоненты. Появился self-hosted Penpot (kind-стенд, MCP-сервер с
агентскими скиллами `penpot-*` в `.opencode/skills/`), в котором агент начал
строить дизайн-систему. Возник риск: **второй источник визуальной истины** —
если агент изобретает токены в Penpot, код и макеты неизбежно разъедутся
(аналог «два Postgres в одном кластере» — удвоение ops-поверхности).

Вопрос: где живёт канон визуальных решений и как встроить Penpot в пайплайн
«запрос → аналитика → ADR → issue → разработка → ревью» (ADR-0002, конвенции
`docs/adr/README.md`) без появления несогласованной параллельной дизайн-системы?

## Decision Drivers

- Агенты пишут весь UI-код; дисциплина не работает — нужны машинно-проверяемые барьеры (как CI-гейт `adr-order`)
- AntD 6 уже владеет реальной токен-системой в типизированном коде (`ThemeConfig`); дефолтная дизайн-система AntD принята как основа (ADR-0002, «минимализм»)
- Penpot нужен как стенд для эскизов и согласования экранов до написания кода
- Drift «канон ↔ зеркало» должен обнаруживаться автоматически
- Правило порядка работ: docs-артефакты (ADR, design-контракт) — отдельно и до реализации (CI-гейт `adr-order`)

## Considered Options

- **A. Код — канон, Penpot — зеркало** (рекомендуется)
- B. Penpot — канон, код импортирует токены из Penpot library (design-to-code pipeline)
- C. Без контракта: агенты работают ad-hoc, макеты — по желанию

## Decision Outcome

Chosen option: **A. Код — канон, Penpot — зеркало**, потому что AntD 6 уже
фиксирует токены в типизированном коде (`theme.ts`, `colors.css`), агенты пишут
код от типизированной темы надёжнее, чем от экспорта, а drift проверяется в
одну сторону. Penpot не источник истины, а (1) зеркальная библиотека — модель
дефолтной дизайн-системы AntD с brand-оверрайдами из `theme.ts`, и (2) стенд
эскизов для согласования экранов ДО разработки.

### Consequences

* Good, потому что единый источник истины: то, что в проде, определяется `theme.ts` + AntD defaults
* Good, потому что UI-фичи получают этап визуального согласования (эскиз в Penpot) в пайплайне до issue на код
* Good, потому что drift код↔макет проверяется скриптом, а не глазами
* Bad, потому что Penpot-библиотека — ручная работа по поддержанию актуальности (смягчается скиллами `penpot-generate-library` / `penpot-generate-design` и drift-гейтом)
* Neutral, потому что кастомная токен-таксономия (W3C DTCG) не вводится — AntD tokens + `--bigbug-*` достаточны; пересмотр при появлении реальной потребности (вторая платформа, дизайнеры вне AntD)

## Правила (нормативная часть)

1. **Канон токенов**: `frontend/src/theme.ts` (AntD `ThemeConfig`) + `frontend/src/colors.css` (`--bigbug-*`). Новые визуальные константы попадают ТОЛЬКО туда (docs- или implementation-PR по обычному пайплайну), в компонентах — ссылка на токен AntD/CSS-переменную, а не литерал.
2. **Агентский визуальный контракт**: `docs/design/design.md` (English, для агентов) — обязателен к прочтению перед любой UI-работой; скиллы `penpot-*` — исполнители.
3. **Penpot-библиотека** строится скиллом `penpot-generate-library` ИЗ кода (AntD defaults + `theme.ts`), зеркалит канон, не изобретает токены. Экраны (`penpot-generate-design`) собираются только из library-компонентов с привязкой к токенам.
4. **Пайплайн UI-фичи**: аналитика (US/UC) → при изменении визуального языка — docs-PR (этот ADR / design.md) → эскиз экрана в Penpot (issue на дизайн-фазу) → согласование владельцем → issue на реализацию (обязательное поле «ссылка на Penpot frame») → код → ревью (скриншот `export_shape` из Penpot vs реализация).

## Confirmation

- CI-гейт `design-tokens` (issue:lint-запрет raw hex/px вне `theme.ts`/`colors.css` в `frontend/src/components|pages`) — падает PR с литералами.
- `make check-tokens` (issue: drift-проверка «theme.ts + colors.css ↔ экспорт токенов Penpot library» через Penpot MCP) — падает при расхождении.
- Шаблон plan-issue получает секцию Penpot (issue: обновление шаблона) — UI-issue без ссылки на frame не принимается.
- Проверка порядка: docs-артефакты этого ADR идут отдельным docs-PR (`make check-adr-order` — уже существует).

## More Information

- ADR-0002 (frontend stack, AntD 6), конвенции ADR `docs/adr/README.md`, CI-гейт `adr-order`.
- Инфраструктура Penpot: kind-стенд, деплой `~/Projects/DevBuild/penpot/`, MCP через `https://penpot.local/mcp/stream?userToken=...` (dev-инструмент, вне прод-периметра; TLS — ADR-0030, общий CA).
- Агентские скиллы: `.opencode/skills/penpot-*` (vendored из penpot-skills, совместимы с opencode).
