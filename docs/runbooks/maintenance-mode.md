# Runbook: Maintenance mode

> Minimal maintenance mode (issue #114): a DB flag stops the schedulers from
> enqueueing new task passes. Queued tasks already in Redis Streams persist
> across the whole window; workers drain the backlog on startup. 503-middleware
> and `/ready` behavior are explicitly out of scope for this iteration.

## Turn maintenance mode on

1. Toggle the flag (admin UI or API):

   ```bash
   curl -X PATCH https://api.local/api/admin/maintenance \
        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
        -d '{"maintenance_mode": true}'
   ```

2. Scale workers to 0 (manual — no k8s API integration yet):

   ```bash
   kubectl --context kind-bigbug-dev -n bigbug scale deploy bigbug-worker --replicas=0
   ```

The flag is picked up by scheduler passes within the 30 s cache TTL; running
tasks finish their current pass. No new tasks are enqueued; the existing Redis
Streams backlog is untouched.

## Check state

```bash
curl https://api.local/api/status/maintenance   # public banner endpoint, no auth
curl https://api.local/api/admin/maintenance -H "Authorization: Bearer $TOKEN"
```

## Turn maintenance mode off

1. Scale workers back up:

   ```bash
   kubectl --context kind-bigbug-dev -n bigbug scale deploy bigbug-worker --replicas=1
   ```

2. Toggle the flag off:

   ```bash
   curl -X PATCH https://api.local/api/admin/maintenance \
        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
        -d '{"maintenance_mode": false}'
   ```

Scheduled passes resume; workers drain the persisted backlog first.

## Notes

- Every toggle writes an audit event (`platform_settings` / `maintenance_mode`).
- Stuck runs after a long window: recover via Sync Runs page (retry/requeue),
  see the Operations Console runbook.

## PEL reaper (issue #116)

> Automatic recovery for tasks lost when a worker died without ack and the
> broker's own autoclaim missed them (taskiq-redis #131 territory). Non-admin:
> no operator action required, this section is for observing and troubleshooting.

A scheduled pass (every 10 min, `reaper_cron`) inspects the broker's Redis
Stream consumer group: entries pending longer than `task_idle_timeout_ms`
(30 min) are force-claimed via XAUTOCLAIM, re-added to the stream, and the
old entry acked — the task is re-executed within ~idle_timeout of the
original failure. No admin action is needed for a SIGKILLed worker.

### What to monitor

Each pass emits one structured log line (bigbug-backend / worker logs):

```
reaper pass: stream_len=<XLEN> pel_size=<PEL size> oldest_pending_ms=<age> reclaimed=<n> poison=[...]
```

- `reclaimed > 0` — tasks were re-delivered after a stuck window; correlate
  with the Sync Runs page (the re-delivered run reuses its `sync_runs` row,
  attempts incremented).
- `poison=[...]` — entries that exceeded the reclaim ceiling
  (`reaper_poison_max_reclaims`, default 3): acked WITHOUT re-delivery,
  logged as ERROR, and written as an outbox event (`task_reap_poison`,
  dedup key `reaper:poison:<task>` — visible via Sync Runs / audit events).
  Poison entries need manual investigation: the task crashed repeatedly
  after the worker picked it up.

### Manual verification (SIGKILL drill)

1. Enqueue a long task (or wait for a scheduled sync).
2. SIGKILL the worker pod mid-run:
   `kubectl --context kind-bigbug-dev -n bigbug delete pod -l app=bigbug-worker --force --grace-period=0`
3. Wait ~30 min (`task_idle_timeout_ms`); the next reaper pass re-delivers
   the task and it completes. Confirm via the pass log line
   (`reclaimed >= 1`) and the Sync Runs page.
