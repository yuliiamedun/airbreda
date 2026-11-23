# AirBreda

Cloud platform for the System Design & Cloud Platforms elective (Year 3 ADSAI, BUas).

Ingests two live Dutch open data streams, stores and processes them, and serves an
ML model that predicts NO₂ exceedance risk for the A27 interchange near Breda.

## Data sources

| Source | Endpoint | Data |
|---|---|---|
| RIVM Luchtmeetnet | `https://api.luchtmeetnet.nl/open_api/stations/NL10240/measurements` | NO₂ hourly readings, station NL10240 (Breda-Tilburgseweg) |
| NDW Open Data | `http://opendata.ndw.nu/` (`snelheden_en_intensiteiten_*`) | Vehicle intensities & speeds, four A27 sites near hm 63 |

Neither requires an API key. Luchtmeetnet fair use: 100 requests / 5 minutes.

## Cloud provider

AWS — home region `eu-north-1` (Stockholm). Services outside the home region are denied.

## Layout

```
docs/                 Architecture Design Document (published via GitHub Pages)
  index.md            Architecture overview + diagram
  lab-notebook.md     Per-day lab answers
  adr/                Architecture Decision Records
ingest_air.py         Luchtmeetnet NO2 ingestion
ingest_traffic.py     NDW traffic ingestion
tests/                pytest suite
Dockerfile            Container for the ingestion service
```

## Running

```bash
pip install -r requirements.txt
python ingest_air.py
```

Containerised:

```bash
docker build -t airbreda-air .
docker run airbreda-air
```

Tests:

```bash
pytest tests/ -v
```
