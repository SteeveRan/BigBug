---
artifact: use-case
version: "1.0"
module: git-mirroring
id: UC-gitmrr-009
---

# UC-gitmrr-009: Обнаружить осиротевшие зеркала

## Header

| Поле | Значение |
|-------|-------|
| ID | UC-gitmrr-009 |
| Название | Обнаружить осиротевшие зеркала |
| Уровень цели | user-goal |
| Область | Модуль Git Mirroring |
| Первичный актор | admin |
| Вторичные акторы | GitLab API (целевые инстансы) |
| Трассировка | US-gitmrr-009 |

> **Статус: discovery — норматив этого модуля; remediation (бывшие шаги 3–4)
> перенесена в #160** (grill #140, отдельный ADR-кандидат) — см. US-gitmrr-010
> (moved) и таблицу «Orphaned remediation» в каталоге edge cases.

## Preconditions

- Admin имеет право управления orphaned (discovery).
- Существует минимум один активный GitLab-провайдер.

## Success Guarantee (Postconditions)

- Осиротевшие проекты перечислены с деталями обнаружения.
- Минимальная гарантия: сбои discovery никогда ничего не изменяют.

## Trigger

Admin открывает orphaned-страницу и запускает discovery.

## Main Success Scenario

| Шаг | Актор | Система |
|------|-------|--------|
| 1 | Admin запускает discovery | |
| 2 | | Система сканирует каждого активного GitLab-провайдера и перечисляет проекты, чьи id не ссылается ни одно зеркало |

## Extensions (Alternative Flows)

| На шаге | Условие | Обработка |
|---------|-----------|----------|
| 1 | Ни одного GitLab-провайдера не настроено | Система обязана показать действенный empty state со ссылкой в настройки провайдеров (EC-gitmrr-032) |
| 2 | Один провайдер недоступен | Система обязана вернуть результаты доступных провайдеров и отдельно сообщить о сбойном (EC-gitmrr-033) |
| 1 | У пользователя нет права | Система обязана отклонить с 403 (EC-gitmrr-019) |

## Related Artifacts

- User stories: [US-gitmrr-009](../../stories/git-mirroring/US-gitmrr-009.md); remediation — US-gitmrr-010 (moved to #160)
- Edge-case строки: docs/analitics/edge-cases/git-mirroring.md «Orphaned discovery»
- Открытые вопросы: дизайн remediation-эндпоинтов / семантика ошибок — grill #140, владелец — #160
