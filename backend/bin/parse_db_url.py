#!/usr/bin/env python3
"""Print DATABASE_URL fields as TAB-separated ``host\\tport\\tuser\\tdb``.

Used by bin/entrypoint.sh (parse_database_url): a Python parse is robust
against URL-encoded credentials and IPv6 hosts, where shell regexes fail.
Stdlib only — same contract as the previous inline heredoc.
"""

import sys
from urllib.parse import unquote, urlparse

raw = sys.argv[1]
# Strip SQLAlchemy dialect (e.g. "postgresql+asyncpg") so urlparse sees a
# scheme it can reason about.
scheme, _, rest = raw.partition("://")
base_scheme = scheme.split("+", 1)[0]
url = urlparse(f"{base_scheme}://{rest}")

host = url.hostname or ""
port = url.port or 5432
user = unquote(url.username or "")
db = (url.path or "/").lstrip("/")

if not host:
    sys.stderr.write("DATABASE_URL is missing host component\n")
    sys.exit(1)

print(f"{host}\t{port}\t{user}\t{db}")
