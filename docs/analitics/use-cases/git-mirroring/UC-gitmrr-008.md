---
artifact: use-case
version: "1.0"
module: git-mirroring
id: UC-gitmrr-008
---

# UC-gitmrr-008: Проверить целостность зеркала

## Header

| Поле | Значение |
|-------|-------|
| ID | UC-gitmrr-008 |
| Название | Проверить целостность зеркала |
| Уровень цели | user-goal |
| Область | Модуль Git Mirroring |
| Первичный актор | operator |
| Вторичные акторы | Git-провайдер API (источник), GitLab API (цель) |
| Трассировка | US-gitmrr-007 |

## Preconditions

- Operator имеет право integrity-check.
- У зеркала есть привязанный целевой проект.

## Success Guarantee (Postconditions)

- Вердикт (MATCH / MISMATCH / ERROR) записан; состояние зеркала его отражает.
- Минимальная гарантия: сбойная проверка не подделывает MATCH.

## Trigger

Operator триггерит integrity check.

## Main Success Scenario

| Шаг | Актор | Система |
|------|-------|--------|
| 1 | Operator триггерит integrity check | |
| 2 | | Система читает HEAD-коммит default-ветки источника через source-провайдера |
| 3 | | Система читает HEAD-коммит целевого проекта через GitLab API |
| 4 | | Система записывает MATCH или MISMATCH (увеличивая счётчик расхождений), обновляет состояние зеркала и сообщает вердикт |

## Extensions (Alternative Flows)

| На шаге | Условие | Обработка |
|---------|-----------|----------|
| 2 | Источник нечитаем | Система обязана записать ERROR с причиной провайдера (EC-gitmrr-030) |
| 3 | Цель недоступна или не привязана | Система обязана записать ERROR / отказаться с объяснением «не готов к sync» соответственно (EC-gitmrr-031) |
| 1 | У пользователя нет права | Система обязана отклонить с 403 (EC-gitmrr-018) |

## Related Artifacts

- User stories: [US-gitmrr-007](../../stories/git-mirroring/US-gitmrr-007.md)
- Edge-case строки: docs/analitics/edge-cases/git-mirroring.md «Integrity-проверка»
