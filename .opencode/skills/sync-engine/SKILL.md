---
name: sync-engine
description: Rules for writing background task bodies against sync_engine.py in BigBug. Use when writing or reviewing taskiq tasks, sync/cleanup/freshness task bodies, or anything that imports sync_engine. Guardrail 4 of ADR-0039.
---

# Sync Engine — task body rules (ADR-0039, guardrail 4)

Background tasks execute via taskiq + Redis Streams (at-least-once). The sync core is
`backend/app/services/sync_engine.py`. See [ADR-0039](../../../docs/adr/backend/0039-background-tasks-taskiq-redis-streams.md)
for the full decision.

## Rules for task bodies

1. **Idempotency is mandatory.** Delivery is at-least-once: a task may run twice
   (worker crash after execution, before ack). A repeated run must not duplicate
   side effects — write through existing status/log tables (upsert or status-flag
   transitions), never blind inserts.
2. **Delegate to `sync_engine.py`; keep bodies thin.** A task body resolves
   arguments, calls the engine, and records the outcome. No business logic in the
   task body.
3. **No result backend.** Status truth is PostgreSQL (log tables + status flags
   0–4). Never publish results to the queue and never read task status from Redis.
4. **No DLQ assumptions.** Retry exhaustion (`max_retries=3`) leaves only logs and
   a failed status flag. If a failure needs manual triage, say so in the log entry.

## Forbidden imports in sync core (`sync_engine.py`)

Lint bans these (guardrail 3, enforced in `make lint`):

- `fastapi`, `starlette`, any `app.api.*` — no API layer in the core
- `apscheduler` — scheduling is enqueue-only; the engine never schedules
- blocking I/O without async wrapper (requests, stdlib http) — async stack only
  (ADR-0001)
- taskiq itself — the engine executes, it does not enqueue

## Broker contract (do not change per-task)

`ack_type="when_executed"`, `max_retries=3`, `idle_timeout=30 min`
(must exceed max task duration), explicit `unacknowledged_lock_timeout`
(taskiq-redis #131), `DummyResultBackend`. Changing these requires an ADR update.

## Workflow

- New background work → new taskiq task with a thin body calling `sync_engine.py`.
- Editing sync execution semantics → read ADR-0039 first; contradicting it requires
  a new ADR, not a code change.
