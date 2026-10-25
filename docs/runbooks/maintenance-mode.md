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
