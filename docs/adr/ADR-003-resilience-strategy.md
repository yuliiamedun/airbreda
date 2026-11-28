# ADR-003: Resilience Strategy

## Context

AirBreda runs on one EC2 virtual machine and one RDS database, both in the same Availability Zone in eu-north-1. The December 2021 AWS outage showed that services can fail together when they share infrastructure. AirBreda has the same risk: one VM runs all three containers, and one database stores all NO₂ readings.

The dashboard updates hourly and is not safety-critical, so a short outage is not a major issue. However, it is a public tool for the municipality, and a broken dashboard could damage trust. I need to balance reliability with cost: the current system costs around $27 per month, while a standby setup would almost double that.

## Decision

SLO: 99% availability for GET /site/{id}. This means 99% of requests should return a valid response, allowing around 7.2 hours of downtime per month (432 minutes).

I did not choose 99.9% availability (43 minutes of downtime per month). A single VM restart or failed update could exceed that limit, and meeting it would require a second machine.

DR tier: Backup & Restore. I do not keep a backup server running. Instead, I rely on resources stored separately from the VM:
- Database: RDS automated backups allow me to restore the database to an earlier point in time.
- Code and model: GitHub stores the application, Dockerfiles and model.pkl, so I can rebuild the VM if it fails.
- Traffic data: NDW CSV files are stored in S3 and survive a VM failure.
Targets: RTO 2 hours, RPO 1 hour.
- RTO is the target time to restore the system. Rebuilding the VM manually on Day 3 took about an hour, including installing Docker, copying files, building images and setting up cron. Two hours gives me extra time to diagnose the problem.
- RPO is how much recent data I can afford to lose. Since ingestion runs hourly, I could lose the run that was in progress when the system failed.
A two-hour outage uses about 28% of the monthly downtime allowance. This means the 99% SLO can still be met after three such incidents in one month.

**Why I chose this tier**  
A 99% SLO allows several hours of downtime per month, and Backup & Restore can recover the system within that time. A more advanced setup would reduce recovery to around 15 minutes, which the current SLO does not require.

**Rejected:**  
Warm Standby. This option would keep a second VM and a database replica running in another Availability Zone, reducing recovery time to around 15 minutes. I rejected it because it would almost double the cost without being necessary for the current SLO. I would consider it if the municipality required higher availability.

## Consequences

- **Recovery is manual and depends on me.** Nothing fails over automatically. Someone has to notice the outage (through `/health` or `cron.log`), launch a new VM and redeploy. The `.env` file with the database password is not in the repository, so it must be restored from my laptop.
- **Cost of the next tier up.** In USD at AWS list prices for eu-north-1 (VM, database and public IPs only), the current stack costs about $26.86 per month. Pilot Light, the next tier up, would keep a Multi-AZ database replica running but the standby VM switched off as a saved image, adding roughly $12–13 per month (about $39 in total). Warm Standby adds about $23.94 per month (a second running t3.micro, a Multi-AZ database and a third public IP), for about $50.81 in total.
- **Data loss differs by source.** Missing Luchtmeetnet hours are recovered by the next run, which re-fetches a 10-hour window, and `ON CONFLICT DO NOTHING` prevents duplicates. NDW is a live snapshot, so readings during an outage are lost permanently, and no DR tier can recover them. This leaves gaps in the training data but does not corrupt it.
- **Region risk.** Neither this tier nor Warm Standby covers a regional outage. A 5-hour regional outage like 2021 would use about 5.7% of the annual budget (5 of 87.6 hours) with no way to fail over. My account restricts services to eu-north-1, so a cross-region setup is not available to me.
- **Monitoring.** `cron.log` records each ingestion run, and the dashboard's `/health` endpoint shows the last successful fetch and bad-data count for both sources, which is how an outage would be noticed.