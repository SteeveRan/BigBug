# Аналитика — реестр документов

Нормативный пользовательский слой: user stories, use cases, edge cases.
Правила процесса — в [AGENTS.md](../../AGENTS.md) («Analytics vs architecture»)
и скиллах `deliver-user-stories` / `deliver-use-cases` / `deliver-edge-cases`.

## Язык

Аналитика пишется **по-русски** (требование владельца, 2026-10-27). В английском
остаются: ID артефактов (`US-<module>-NNN`, `UC-…`, `EC-…`), permissions,
статусы (`FRESH`/`STALE`/`MATCH`…), идентификаторы кода, технические термины
без устоявшегося эквивалента.

## Структура

```
docs/analitics/
├── README.md            # этот реестр
├── stories/<module>.md  # user stories (US-<module>-NNN)
├── use-cases/<module>.md# use cases (UC-<module>-NNN)
└── edge-cases/<module>.md # каталог отказов (EC-<module>-NNN)
```

- Файлы ленивые: создаются при появлении аналитики модуля, пустые не заводить.
- ID стабильны: перенумерация запрещена; удаление — только `status: retired`.
- При >10 use cases в модуле — раскладка в `use-cases/<module>/` + индекс.

## Правила для агентов

1. Новая аналитика — по скиллам, на русском, с записью в таблице ниже (в том же PR).
2. Аналитика — норматив: код обязан соответствовать; расхождение кода со строкой
   аналитики делает PR некорректным (возврат). Аналитика никогда не «догоняет код».
3. ADR ссылается на мотивирующие строки аналитики; аналитика на ADR не ссылается.
4. Добавление строк/артефактов для найденных пробелов — аддитивно, с явным
   принятием ревьюером в том же PR.

## Реестр модулей

| Модуль | Stories | Use cases | Edge cases | Issue | Статус |
|---|---|---|---|---|---|
| git-mirroring | [stories/git-mirroring.md](stories/git-mirroring.md) | [use-cases/git-mirroring.md](use-cases/git-mirroring.md) | [edge-cases/git-mirroring.md](edge-cases/git-mirroring.md) | #159 | в ревью (PR #175) |
| user-profile | — | — | — | #158 | не начата |
| orphaned-remediation | — (владелец: #160, отправная точка — moved-строки в git-mirroring) | — | — | #160 | не начата |
| image-builds | — | — | — | #163 | не начата |
| gitlab-projects | — | — | — | #164 | не начата |
| providers | — | — | — | #165 | не начата |
| reports | — | — | — | #166 | не начата |
| admin-rbac | — | — | — | #167 | не начата |
| docker-sync | — | — | — | #169 | не начата |
| helm-sync | — | — | — | #170 | не начата |
