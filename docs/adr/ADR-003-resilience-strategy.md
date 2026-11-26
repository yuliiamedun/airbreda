# ADR-003: Resilience Strategy

## Context
AirBreda runs on one EC2 VM and one RDS database in a single region (eu-north-1). The
December 2021 AWS us-east-1 outage showed that services which look independent fail
together when they share infrastructure. The dashboard refreshes hourly and is not
safety-critical, so a short outage costs little. It is a public-sector tool for the
municipality, so a visibly broken dashboard still damages trust.

## Decision
- **SLO:** 99% availability of GET /site/{id}, measured as the share of requests that
  return a valid response. The error budget is about 7.2 hours per month (432 min).
  I did not choose 99.9% (43 min per month): one reboot or failed update on a single
  VM could use it up, and meeting it needs a second machine.
- **DR tier: Warm Standby.** A scaled-down but always-running copy of the stack: a
  small standby VM with both containers installed, and a standby database replica in a
  second Availability Zone. On failure, traffic moves to the standby and the replica is
  promoted to primary.
- **Targets:** RTO 15 minutes, RPO 1 hour. Because ingestion is hourly and idempotent
  (ON CONFLICT DO NOTHING), the standby can re-fetch the missed window without
  creating duplicates.
- **Honest note:** this tier is stronger than a 99% SLO strictly requires. I chose it
  because a 15-minute RTO keeps one incident to a small part of the monthly budget,
  and for a municipal service the extra cost is easier to defend than a visible outage
  of several hours. If cost became the main concern, I would step down to Pilot Light.
- **Rejected: Backup & Restore.** It is the cheapest, but rebuilding the VM by hand
  took about an hour on Day 3. That would give an RTO of hours and use much of the
  budget in one incident.

## Consequences
- **Cost (USD, AWS list prices for eu-north-1; VM, database and public IPs only):**
  the current stack costs about $26.86 per month. Warm Standby adds about $23.94 per
  month (a second t3.micro VM, a Multi-AZ database and a third public IP), for about
  $50.81 in total. The next tier up, Active-Active, runs two full stacks serving
  traffic at once: about $53.73 plus a load balancer. At this instance size the two
  tiers cost nearly the same, because there is nothing smaller to scale down to.
  Active-Active mainly adds a load balancer and data-sync complexity.
- **Region risk:** a second Availability Zone covers a data-centre failure but not a
  regional outage. A 5-hour regional outage like 2021 would use about 5.7% of the
  annual budget (5 of 87.6 hours) with no way to fail over. My account restricts
  services to eu-north-1, so a cross-region standby is not available to me.
- **Not built:** this ADR records a design decision. The standby is not deployed in
  this course project, and the diagram shows only what is deployed.
- **Data loss differs by source:** missing Luchtmeetnet hours are recovered by the
  next run, which re-fetches a 10-hour window. NDW is a live snapshot, so readings
  during an outage are lost permanently, and no standby can fix that. This leaves gaps
  in the training data but does not corrupt it.
- **Monitoring:** cron.log shows each run, and the Day 4 /health endpoint will show
  the last successful fetch for both sources.