# Lab Notebook

---

## Day 1 — System Thinking, Cloud Fundamentals, Storage

### Pre-lab estimation exercise

> A team runs a Kubernetes cluster 24/7 for a job that only executes between 08:00 and
> 20:00. The cluster costs €500/month. How much is wasted? How would you fix it?

**Waste:** the job runs 12 of 24 hours, so the cluster is idle 50% of the time →
**€250/month** (€3,000/year). This assumes cost is purely time-based, which holds for
a fixed-size node pool billed per hour; it ignores fixed costs such as the managed
control plane fee.

**Fix:**

- Scheduled scaling — scale the node pool to zero at 20:00, back up at 08:00
  (AWS Auto Scaling scheduled actions; AKS node pool autoscaler on Azure).
- Cluster Autoscaler to drop idle nodes automatically.
- Spot instances for the active window, since the job is batch and fault-tolerant
  (70–90% off on-demand).

Realistic saving: ~€250/month from scheduling, more with Spot, minus the control plane fee.

---

### Lab 1 — Follow task

**1. Cloud account:** AWS free tier. Home region `eu-north-1`.

**2. CLI auth:** `aws sts get-caller-identity` → _paste identity (redact the account ID)_

**3. Docker:** `docker run hello-world` → ✅ ran successfully.

**4. Luchtmeetnet API** (`SystemDesign/getNO2Readings.py` in the course repo — the task
text calls it `extract.py`):

| Question | Answer |
|---|---|
| What fields does a single measurement record contain? | |
| What is the time resolution? | |
| What happens if you request a `formula` the station doesn't measure? | |
| How recent is the latest reading compared to when you ran the script? | |

---

### Lab 1 — Extend task

- [ ] `ingest_air.py` — NO₂ only, prints latest reading with timestamp
- [ ] `Dockerfile` — installs `requests`, calls the live API on each run
- [ ] Error handling for timeouts and failed requests
- [ ] Comment: CAP trade-off of the sensor network + handling null/missing values in production
- [ ] `tests/test_ingest_air.py` passing

**CAP trade-off of the sensor network:**

**Handling null / missing values in production:**

---

### Day 1 wrap-up

**1. A colleague says "Let's use DynamoDB — it scales infinitely." Three questions to ask first:**

**2. Five years, 10 stations — estimated row count in `sensor_readings`. Does this change the database choice?**

**3. Most recent NO₂ value for station NL10240:**
