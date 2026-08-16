"""
Guard актуальности зафиксированного OpenAPI-контракта.

``backend/openapi.json`` — источник истины контракта фронт-бэк. Этот тест
генерирует схему тем же способом, что и ``scripts/export_openapi.py`` (импорт
приложения + ``app.openapi()``), и сравнивает её с зафиксированным файлом как
объекты Python, чтобы не зависеть от форматирования/порядка ключей в JSON.

При расхождении схема считается устаревшей — нужно перегенерировать её:
``backend/scripts/export-openapi.sh``.
"""

import json
from pathlib import Path

from app.main import app

# Путь к зафиксированной схеме относительно этого файла:
# tests/unit/test_openapi_contract.py -> ../../../openapi.json
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
CONTRACT_FILE = BACKEND_DIR / "openapi.json"


def test_openapi_schema_matches_committed_contract():
    """Зафиксированный openapi.json должен совпадать с текущей схемой приложения."""
    assert CONTRACT_FILE.is_file(), (
        f"Файл контракта не найден: {CONTRACT_FILE}\n"
        "Сгенерируйте его: backend/scripts/export-openapi.sh"
    )

    with CONTRACT_FILE.open(encoding="utf-8") as fh:
        committed = json.load(fh)

    current = app.openapi()

    assert current == committed, (
        "OpenAPI-схема устарела: backend/openapi.json не соответствует текущему "
        "состоянию приложения. Запустите backend/scripts/export-openapi.sh, чтобы "
        "перегенерировать схему."
    )
