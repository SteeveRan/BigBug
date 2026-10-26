---
artifact: user-stories
version: "1.0"
created: 2026-10-26
status: complete
context: User stories модуля Git Mirroring (GitHub → GitLab). Мотивирующий issue #159, часть аналитической волны #154. Архитектурное решение: ADR-0008.
---

# User Stories: Git Mirroring

User stories модуля Git Mirroring: зеркалирование репозиториев GitHub в GitLab, поддержание актуальности, проверка целостности и восстановление после расхождений. Персоны — платформенные роли: admin, operator, viewer.

Потоки — в [use cases](../../use-cases/git-mirroring/); поверхность отказов — в [edge cases](../../edge-cases/git-mirroring.md). Отчёты по зеркалам — отдельный модуль (issue #166): story US-gitmrr-009 покрывает только видимость журналов конкретного зеркала, но не страницы Reports.

---

## Список stories

| ID | Название | Примечание |
|----|----------|------------|
| [US-gitmrr-001](US-gitmrr-001.md) | Импортировать группу источников из Git-провайдера | |
| [US-gitmrr-002](US-gitmrr-002.md) | Создать зеркало для source-репозитория | |
| [US-gitmrr-003](US-gitmrr-003.md) | Массово создать зеркала | |
| [US-gitmrr-004](US-gitmrr-004.md) | Запустить sync зеркала вручную | |
| [US-gitmrr-005](US-gitmrr-005.md) | Настроить автоматический sync через sync-группу | |
| [US-gitmrr-006](US-gitmrr-006.md) | Проверить свежесть зеркала | |
| [US-gitmrr-007](US-gitmrr-007.md) | Проверить целостность зеркала | |
| [US-gitmrr-008](US-gitmrr-008.md) | Отслеживать результаты sync зеркала | |
| [US-gitmrr-009](US-gitmrr-009.md) | Обнаружить осиротевшие GitLab-проекты | |
| [US-gitmrr-010](US-gitmrr-010.md) | Перепривязать или удалить осиротевшее зеркало | moved to #160 |
| [US-gitmrr-011](US-gitmrr-011.md) | Удалять и восстанавливать зеркала безопасно | |
| [US-gitmrr-012](US-gitmrr-012.md) | Усыновить существующий GitLab-проект как зеркало | |
