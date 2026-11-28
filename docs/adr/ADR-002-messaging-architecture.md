# ADR-002: Messaging Architecture

## Context
AirBreda has two ingestion containers: air (Luchtmeetnet) and traffic (NDW). Each fetches from its own source and writes straight to its own store (RDS or S3). If a second consumer of the readings is added later (an ML model, an alerting service), each consumer would have to be wired into the ingestion code. A message broker between producers and consumers removes that coupling. The current load is small: one air station and four traffic sites, polled hourly, on a single 1 GB VM.

## Decision
No message queue is part of the deployed system. Both containers write directly to RDS and S3.

I considered Redis (redis:7-alpine, one container) as the broker for the Day 2 lab, because it needs no cloud setup. I wrote a Docker Compose setup with a Redis container for the lab but did not run it end to end, so this evaluation rests on the course material rather than my own measurements. For a real deployment I would choose AWS SQS: it is managed, so there is no broker to run, patch or keep alive, and at this volume its per-request price is negligible. I rejected Redis for production because we would own its uptime, and its messages live in memory, so a restart can lose them unless persistence is configured.

## Consequences
- **Simpler setup:** nothing extra to run, monitor or pay for, and one fewer failure point on a small VM.
- **Harder:** adding a second consumer means changing the ingestion code. I would bring the queue back when a second consumer exists or ingestion outgrows one VM.
- **If the broker went down** (in the evaluated design), publishing would fail and each reading would have to be retried or lost. In the deployed design the failure points are RDS and S3 instead:
  - RDS unreachable: Logged as `db_write_failed`. The next run fetches the last 10 hours again, and `ON CONFLICT DO NOTHING` fills the gap without duplicates.
  - S3 upload fails: Logged as `site_failed`. That hour's traffic reading is lost because NDW only provides live snapshots.
- **Bad data is handled differently on purpose.** Luchtmeetnet's stale or null readings are stored with `is_flagged = TRUE`, since they show a real gap in the data. NDW speeds of -1 are excluded from the average because they are invalid values that would distort it. I would keep this approach but also archive the original NDW XML so these values can be recovered later. This is a known limitation in `ingest_traffic.py`.