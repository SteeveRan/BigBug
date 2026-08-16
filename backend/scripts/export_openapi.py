#!/usr/bin/env python3
"""
Экспорт OpenAPI-схемы FastAPI-приложения в детерминированный JSON-файл.

Схема — источник истины контракта фронт-бэк. Этот скрипт генерирует её без
подключения к БД/Redis и без запуска lifespan: импортируется приложение
(``from app.main import app``) и вызывается ``app.openapi()``, который лишь
строит схему из задекларированных роутеров/Pydantic-моделей.

Запуск (из ``backend/``)::

    python -m scripts.export_openapi            # -> backend/openapi.json
    python -m scripts.export_openapi -o /tmp/schema.json
    python scripts/export_openapi.py            # эквивалентно первому
"""

import argparse
import json
import sys
from pathlib import Path

# Make ``app`` importable regardless of invocation style:
#   - ``python -m scripts.export_openapi`` (cwd = backend, works already)
#   - ``python scripts/export_openapi.py``  (sys.path[0] = scripts/, needs fix)
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402  (import must follow sys.path setup)

# HTTP-методы, которые FastAPI считает операциями OpenAPI.
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def count_operations(schema: dict) -> int:
    """Подсчитать количество операций (методов) во всех paths схемы."""
    total = 0
    for path_item in schema.get("paths", {}).values():
        total += sum(1 for key in path_item if key.lower() in _HTTP_METHODS)
    return total


def build_schema() -> dict:
    """Сгенерировать OpenAPI-схему из FastAPI-приложения."""
    return app.openapi()


def write_schema(schema: dict, output: Path) -> None:
    """Записать схему детерминированно: сортировка ключей + отступы + финальный \\n."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(schema, fh, sort_keys=True, indent=2, ensure_ascii=False)
        fh.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Экспорт OpenAPI-схемы FastAPI-приложения в JSON.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=BACKEND_DIR / "openapi.json",
        help="Путь к выходному файлу (по умолчанию: backend/openapi.json)",
    )
    args = parser.parse_args(argv)

    schema = build_schema()
    write_schema(schema, args.output)

    paths_count = len(schema.get("paths", {}))
    operations_count = count_operations(schema)
    version = schema.get("info", {}).get("version", "unknown")

    print(f"OpenAPI-схема записана в: {args.output}")
    print(f"  paths:      {paths_count}")
    print(f"  operations: {operations_count}")
    print(f"  version:    {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
