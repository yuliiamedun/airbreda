# ADR-004: Compute Strategy

## Context
AirBreda needs two small jobs to run reliably every hour without my laptop: an air
quality fetch (Luchtmeetnet to RDS) and a traffic fetch (NDW to S3). Each takes about a
minute. Day 3 asked me to move them from my laptop to the cloud. The team is one person,
and a managed service would add setup and cost for a workload this small.

## Decision
Run both jobs as Docker containers on one EC2 VM (t3.micro, Amazon Linux 2023, eu-north-1),
started hourly by cron. Access to S3 comes from an IAM role attached to the VM, so no AWS
keys are stored on it. The database accepts connections from the VM's security group
rather than from a fixed IP.

- **Why a VM and not a managed container service** (ECS or Azure Container Apps): I keep
  full control, there is almost nothing new to learn, and the cost is easy to predict.
  The price is that I look after the operating system, Docker and cron myself.
- **Cost:** about $7.88 per month for the VM (USD, AWS list price), or about $11.53 with
  its public IPv4 address. Credits cover this in my account.
- **Redis queue dropped.** ADR-002 describes a queue between ingestion and storage. With
  one consumer (the database), a queue adds a broker to run and monitor and gives nothing
  back. I would bring it back when a second consumer of the readings exists (for example
  an ML model reading live) or when ingestion outgrows a single VM.

## Consequences
- **Operational concern I did not anticipate:** the traffic container was killed with
  exit code 137 (out of memory). The VM has about 900 MB of RAM and the decompressed NDW
  file needed more. It failed silently, with no error line in the log. I fixed it by
  adding a 2 GB swap file and making it permanent in /etc/fstab. A larger instance would
  also work, at roughly double the price.
- **Single point of failure:** one VM means that if it stops, nothing runs. ADR-003
  covers the recovery plan.
- **Cron limitation:** cron starts jobs on time but does not check whether the previous
  run finished.
- **If AirBreda grew to 50 corridors fetched every 5 minutes**, this design would not
  hold. That is about 200 traffic sites instead of 4, and my logs show each site takes
  about 10 to 13 seconds, so one run would take roughly 40 minutes, longer than the
  5-minute interval. Runs would overlap and exhaust memory. I would move to a managed
  container service with scheduled tasks (for example ECS on Fargate), which starts
  containers on schedule, runs several in parallel and replaces failed ones without a
  server to look after. I would also change the code to parse the NDW file once per run
  instead of once per site. Cost and AWS setup effort would both rise.
- **What would trigger the move earlier:** a run time approaching the interval, a need
  for more than one machine, or a reliability target stricter than the 99% in ADR-003.