# ADR-004: Compute Strategy

## Context
AirBreda needs two jobs to run every hour without relying on my laptop: an air-quality fetch (Luchtmeetnet to RDS) and a traffic fetch (NDW to S3). Each takes about a minute. Day 3 required moving them to the cloud. Since this is a small, one-person project, a managed service would add unnecessary setup and cost.

## Decision
I chose to run both jobs as Docker containers on one EC2 VM (t3.micro, Amazon Linux 2023, eu-north-1), scheduled hourly with cron.
The VM uses an IAM role to access S3, so no AWS keys are stored on it. RDS allows connections from the VM's security group instead of relying on a fixed IP.

- **Why a VM and not a managed container service** (ECS or Azure Container Apps): I keep
  full control, there is almost nothing new to learn, and the cost is easy to predict.
  The price is that I look after the operating system, Docker and cron myself.
- **Cost:** about $7.88 per month for the VM (USD, AWS list price), or about $11.53 with
  its public IPv4 address. Credits cover this in my account.
- **Redis queue dropped.** I dropped it because there is only one consumer per data source. It would add another service to maintain without much benefit. I would reconsider it if a second consumer, such as a live ML model, is added.

## Consequences
- **Operational concern I did not anticipate:** The traffic container was killed with exit code 137 because the decompressed NDW file needed more memory than the VM had (around 900 MB). I fixed this by adding a permanent 2 GB swap file. A larger VM would also work but cost roughly twice as much.
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