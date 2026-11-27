# ADR-005: Compute & Deployment Strategy

## Context

In ADR-004, I set up one EC2 t3.micro to run two containers for air quality and traffic data. Now I added a third container for the dashboard and API (FastAPI), which needs to run continuously.

The VM only has 1 GB RAM and 2 GB swap. I added swap on Day 3 after the traffic container ran out of memory.

## Decision

1. **A third container on the same VM, not a managed container service.** 
I chose not to use a managed service like ECS or App Runner because the dashboard is small, has only one user group, and uses the same database and S3 bucket as the other containers. A separate service would add complexity and cost without much benefit right now.  
**What would change my mind.** If AirBreda grows to 50 corridors (around 200 traffic sites) and needs updates every 5 minutes, one VM won't be enough. The traffic job could take around 30 minutes instead of 1, and overlapping runs would use too much memory. A service like ECS with Fargate could distribute this work across multiple containers.  
Even now, memory is quite limited: only around 50 MB remains available while the traffic job runs, which also slows down the dashboard.

2. **Running it long-term:**   
I use `docker run -d --restart unless-stopped`. Docker is enabled at system startup, so the container should restart after a reboot. I haven't tested an actual reboot yet.

3. **What testing locally with Compose caught:**   
When I ran all three containers locally, I noticed a warning that the model was trained with scikit-learn 1.7.2, but the dashboard used 1.9.1. Different versions can cause incorrect predictions. I pinned scikit-learn==1.7.2 in requirements.txt, rebuilt the image, and the warning disappeared. This would have been harder to notice on the VM because the container runs in the background.

4. **Extends ADR-004, does not supersede it:**  
This decision extends ADR-004 rather than replacing it. I still use one VM and Docker containers, but the VM now also runs a dashboard that needs to stay online, not just scheduled jobs. This makes memory management more important because ingestion jobs and the dashboard share the same resources.

## Consequences

- **One VM is a single point of failure for the dashboard too.** If the VM goes down, the live system and the ingestion both stop (see ADR-003).
- **Memory is tight.** The dashboard, a cron container and the swap file share 1 GB. A heavier model or more sites would push this toward a bigger instance or a managed service.
- **Port 8000 is open to my IP only during development.** For assessment it must be opened to the internet, because the marker has to reach it. The page is read-only public data, unauthenticated and served over plain HTTP.
- **Changing IP:** The public IP changes when the VM is stopped and restarted unless I attach an Elastic IP.
- **Retraining requires a rebuild and redeploy** of the dashboard image.