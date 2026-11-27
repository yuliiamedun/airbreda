# AirBreda

Cloud platform for the System Design & Cloud Platforms elective (Year 3 ADSAI, BUas).

AirBreda ingests two live Dutch open-data streams every hour, stores them on AWS, trains a linear regression that estimates NO₂ from traffic and time of day, and serves the readings, the prediction and an exceedance risk for the A27 interchange near Breda on a dashboard and JSON API.

- **Architecture Design Document:** https://yuliiamedun.github.io/airbreda/

## Data sources

| Source | Endpoint | Data |
|---|---|---|
| RIVM Luchtmeetnet | `https://api.luchtmeetnet.nl/open_api/stations/NL10240/measurements` | NO₂ hourly readings, station NL10240 (Breda-Tilburgseweg) |
| NDW Open Data | `http://opendata.ndw.nu/` (`snelheden_en_intensiteiten_*`) | Vehicle intensities and speeds, four A27 sites near hm 63 |

Neither requires an API key. Luchtmeetnet fair use: 100 requests per 5 minutes.

### NDW site-ID mapping

| Site | NDW measurement site ID | Location |
|---|---|---|
| `hrl` | `RWS01_MONIBAS_0271hrl0063ra` | Main carriageway |
| `hrr` | `RWS01_MONIBAS_0271hrr0063ra` | Main carriageway |
| `vwd` | `RWS01_MONIBAS_0270vwd0063ra` | Entry slip road |
| `vwa` | `RWS01_MONIBAS_0270vwa0063ra` | Exit slip road |

## Architecture

| Component | AWS service | Role |
|---|---|---|
| VM | EC2 `t3.micro`, `eu-north-1` | Runs all three containers |
| Database | RDS PostgreSQL `db.t4g.micro` | NO₂ readings (`sensor_readings`) |
| Object storage | S3 | Traffic CSVs (`ndw/YYYY-MM-DD/HH-site.csv`) and the NDW bad-data count (`health/ndw.json`) |
| Access | IAM role `airbreda-vm-role` | S3 upload, download and list on one bucket only |

The two ingestion containers run hourly from cron on the VM. The dashboard runs continuously with `--restart unless-stopped`. See the Architecture Design Document for the diagram and the six ADRs.

## API

| Endpoint | Returns |
|---|---|
| `GET /` | Dashboard: actual NO₂, predicted NO₂ and total traffic |
| `GET /site/{site_id}` | Latest NO₂, the site's traffic intensity, predicted NO₂, exceedance risk (0–1) and timestamp, for `hrl`, `hrr`, `vwd` or `vwa` |
| `GET /health` | Last successful fetch and bad-data count for Luchtmeetnet and NDW |

## Layout

```
docs/                    Architecture Design Document (published via GitHub Pages)
  index.md               Diagram, trade-offs, cloud rationale, costs, reflection
  adr/                   Architecture Decision Records ADR-001 to ADR-006
ingest_air.py            Luchtmeetnet NO₂ ingestion → RDS
ingest_traffic.py        NDW traffic ingestion → S3
getTrafficReadings.py    NDW parsing helpers (provided by the course)
log_utils.py             Structured JSON logging
health.py                Per-container /health endpoint (Day 2)
build_training_data.py   Joins NO₂ and traffic per hour → training_data.csv
train_model.py           Trains the regression → model.pkl
training_data.csv        Training data used for the deployed model
model.pkl                Trained model, baked into the dashboard image
predict.py               Loads model.pkl; returns predicted NO₂ and exceedance risk
dashboard.py             FastAPI dashboard and API
Dockerfile               Air ingestion container
Dockerfile.traffic       Traffic ingestion container
Dockerfile.dashboard     Dashboard container
docker-compose.yml       Local test of all three containers
tests/                   pytest suite
```

## Configuration

All scripts and containers read a `.env` file in the repository root. It is gitignored and must never be committed.

```
DB_HOST=...
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=...
S3_BUCKET=...
```

## Running

Install dependencies:

```bash
pip install -r requirements.txt
```

Run ingestion once:

```bash
python ingest_air.py
python ingest_traffic.py
```

Retrain the model:

```bash
python build_training_data.py
python train_model.py
```

Run the dashboard locally at http://localhost:8000:

```bash
uvicorn dashboard:app --port 8000
```

### Containers

```bash
docker build -t airbreda-air .
docker build -t airbreda-traffic -f Dockerfile.traffic .
docker build -t airbreda-dashboard -f Dockerfile.dashboard .

docker run --rm --env-file .env airbreda-air
docker run --rm --env-file .env airbreda-traffic
docker run -d --name dashboard --restart unless-stopped --env-file .env -p 8000:8000 airbreda-dashboard
```

On the VM, S3 access comes from the IAM role. On a laptop, test all three together with Docker Compose, which shares your local AWS login with the containers:

```bash
docker compose up --build
```

### Tests

```bash
pytest tests/ -v
```