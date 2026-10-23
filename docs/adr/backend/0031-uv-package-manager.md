---
status: proposed
date: 2026-10-23
decision-makers: SteeveRan
---

# Использовать uv как менеджер окружений и пакетов backend

## Context and Problem Statement

Backend управляет виртуальным окружением и зависимостями вручную: `python -m venv .venv` + `pip install -e .` (см. [ADR-0001](0001-choose-backend-stack.md)). Lock-файла нет — каждый разработчик и каждая сборка Docker-образа получают версии пакетов, разрешённые pip на момент установки из диапазонов `>=` в `pyproject.toml`. Следствия:

- окружения разработчиков и Docker-образы **недетерминированы**: два worktree одного агента могут получить разные версии транзитивных зависимостей;
- первый прогон в свежем worktree требует трёх ручных шагов (venv → activate → pip install), которые легко забыть (guard'ы в `backend/scripts/*.sh` только подсказывают команду);
- в `backend/docker/Dockerfile` uv уже использовался, но только как быстрый pip (`uv pip install .`) — без lock это не даёт воспроизводимости.

Как сделать окружения и сборки воспроизводимыми при минимальных изменениях в существующем tooling ([ADR-0019](../common/0019-makefile-tooling-single-entrypoint.md): Makefile — тонкая обёртка, вся env-логика в скриптах)?

## Decision Drivers

* Воспроизводимость: одинаковые версии пакетов во всех worktree, локально и в Docker-образе
* Минимальный diff: Makefile не трогается, паттерн скриптов сохраняется
* Скорость установки (частые пересоздания `.venv` в worktree мульти-агентного workflow)
* Python 3.14 (`requires-python = ">=3.14"`) должен фиксироваться явно

## Considered Options

* Оставить venv + pip, добавить pip-tools (requirements.lock через `pip-compile`)
* Полный переход на uv в проектном режиме (`uv sync` + `uv.lock`)
*uv как drop-in pip (`uv pip install`) без lock-файла

## Decision Outcome

Chosen option: **полный переход на uv в проектном режиме**, because это единственный вариант, дающий воспроизводимость (коммитнутый `uv.lock`) и автоуправление `.venv` без новых файлов-прослойки (requirements.lock пришлось бы синхронизировать с pyproject вручную), при этом Docker уже использовал uv — переход унифицирует tooling.

Конкретика:

- **`backend/uv.lock`** коммитится в git; зависимости ставятся только через `uv sync` (по умолчанию — с dev-группой) или `uv run` (авто-sync перед запуском)
- **Dev-зависимости** переехали из `[project.optional-dependencies].dev` в PEP 735 `[dependency-groups].dev` — идиоматично для uv, `uv sync --no-dev` в Docker работает из коробки
- **`backend/.python-version`** (`3.14`) фиксирует интерпретатор; uv сам скачивает нужный Python при отсутствии
- **Скрипты** `backend/scripts/*.sh`: `VENV_PYTHON=(uv run --project "$BACKEND_DIR" python)`; guard — `command -v uv`; `.venv` создаётся/обновляется автоматически, вручную активировать не нужно
- **Dockerfile**: uv копируется из пиннутого образа `ghcr.io/astral-sh/uv:0.13` (мажор-минор тег, не `latest`), `uv sync --frozen --no-dev --no-editable` ставит ровно версии из `uv.lock`; окружение в `/opt/venv` через `UV_PROJECT_ENVIRONMENT` (структура образа не меняется)
- **Версия uv для локальной разработки не пинится** (гибкая, ставится по docs); формат lock-файла uv поддерживает обратно-совместимо

### Consequences

* Good, because детерминированные окружения: `uv.lock` — единый источник версий для всех worktree, локальных установок и Docker-образа
* Good, because свежий worktree самовосстанавливается: первый `make test-unit-backend` сам создаёт `.venv` из lock
* Good, because установка в ~15ms после кэширования (против минут у pip)
* Bad, because появляется зависимость от внешнего инструмента (uv); участники без uv не смогут работать (mitigated: guard в скриптах подсказывает однострочный install)
* Bad, because `pip install -e .` больше не работает как альтернативный путь — old-инструкции в сторонних материалах устареют
* Neutral, because `.venv` по-прежнему в `backend/.venv` (gitignored), но перестаёт быть контрактом скриптов

### Confirmation

- `backend/uv.lock` существует в git и соответствует `pyproject.toml` (перегенерируется `uv lock`, расхождение ловится `uv sync --frozen` в Docker-сборке).
- Ни один скрипт в `backend/scripts/` не ссылается на `pip install` и `${BACKEND_DIR}/.venv/bin/python` — grep-проверка на ревью: `grep -rn "pip install\|\.venv/bin/python" backend/scripts/` → пусто.
- Docker-сборка детерминирована: `docker build -f backend/docker/Dockerfile backend/` использует `uv sync --frozen` (падает при рассинхроне pyproject/uv.lock вместо тихого резолва).
- Юнит-прогон на новом окружении: `make test-unit-backend` в свежем worktree без `.venv` проходит (окружение создаётся автоматически).

## Pros and Cons of the Options

### Оставить venv + pip + pip-tools

* Good, because нет новых инструментов
* Bad, because requirements.lock — второй файл зависимостей, синхронизируемый вручную; ADR-0001 прямо запрещает requirements-файлы
* Bad, because медленная установка, три ручных шага на worktree

### uv как drop-in pip (без lock)

* Good, because минимальный diff (почти как в Dockerfile до перехода)
* Bad, because не решает главную проблему: версии по-прежнему недетерминированы
* Bad, because `.venv` остаётся ручным шагом

### Полный переход на uv (chosen)

* Good, because lock + speed + автоуправление `.venv` одним инструментом
* Neutral, because uv — быстроразвивающийся инструмент; lock-формат стабилен, Docker-тег пиннут

## More Information

- [ADR-0001](0001-choose-backend-stack.md) — стек backend; правило «requirements-файлы не вводятся» сохраняется, `uv.lock` — lock-файл приложения, а не requirements-файл
- [ADR-0019](../common/0019-makefile-tooling-single-entrypoint.md) — Makefile остаётся тонкой обёрткой; вся venv-логика по-прежнему в `backend/scripts/*.sh`
- uv: https://docs.astral.sh/uv/; PEP 735 (dependency-groups): https://peps.python.org/pep-0735/
- Триггер пересмотра: смена формата `uv.lock` без обратно-совместимости при апгрейде uv (мажорное изменение) — пин Docker-тега обновить осознанно
