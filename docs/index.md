# AirBreda — Architecture Design Document

**Author:** Yuliia Medun
**Course:** System Design & Cloud Platforms, Year 3 ADSAI
**Cloud provider:** AWS (`eu-north-1`)

---

## 1. Problem statement

We want to understand whether traffic congestion at the A27 interchange near Breda
causes air quality exceedances nearby. This document records the design of the cloud
platform that ingests live NO₂ readings (RIVM Luchtmeetnet station NL10240) and live
vehicle counts (four NDW measurement sites at that interchange), stores and processes
them, and serves an ML model predicting NO₂ exceedance risk in the next hour.

---

## 2. Architecture diagram

## 2. Architecture diagram

```mermaid
flowchart LR
    subgraph sources["Data sources"]
        LMN["RIVM Luchtmeetnet API<br/>station NL10240<br/>JSON · hourly NO2"]
        NDW["NDW Open Data<br/>4 sites on A27 (hm 63)<br/>gzipped DATEX II XML · per minute"]
    end

    subgraph vm["EC2 VM · t3.micro · eu-north-1"]
        IA["air container<br/>ingest_air.py · cron hourly"]
        IT["traffic container<br/>ingest_traffic.py · cron hourly"]
        DASH["dashboard container<br/>FastAPI · port 8000<br/>docker run -d --restart unless-stopped<br/>model.pkl baked into image"]
        IAM["IAM role airbreda-vm-role<br/>S3 Put/Get/List on one bucket only"]
    end

    subgraph storage["Storage · AWS eu-north-1"]
        RDS[("RDS PostgreSQL<br/>db.t4g.micro<br/>sensor_readings")]
        S3[("S3 bucket<br/>ndw/YYYY-MM-DD/HH-site.csv")]
    end

    subgraph offline["Laptop · offline training"]
        TR["build_training_data.py<br/>train_model.py<br/>linear regression"]
    end

    USER["Browser / API client<br/>GET / · GET /site/id · GET /health"]

    LMN --> IA
    NDW --> IT
    IA -->|"INSERT ... ON CONFLICT DO NOTHING<br/>port 5432 · security group rule"| RDS
    IT -->|"HTTPS upload"| S3
    DASH -->|"latest NO2 · flagged-row count"| RDS
    DASH -->|"list + read latest CSV per site"| S3
    IAM -.->|"no stored keys"| IT
    IAM -.->|"no stored keys"| DASH
    USER -->|"HTTP :8000 · source IP restricted"| DASH
    RDS -.->|"read rows"| TR
    S3 -.->|"read CSVs"| TR
    TR -.->|"model.pkl copied into the image at build time"| DASH

    classDef src fill:#e8f0fe,stroke:#3b6fd4,color:#11243e
    classDef ing fill:#fff4e5,stroke:#d98324,color:#3d2607
    classDef sto fill:#e9f6ec,stroke:#2f8f4e,color:#0f2e1b
    classDef srv fill:#f3f0f7,stroke:#8b7bb8,color:#2b2340
    classDef off fill:#fdeef0,stroke:#c0475a,color:#3b0f18

    class LMN,NDW src
    class IA,IT,IAM ing
    class RDS,S3 sto
    class DASH,USER srv
    class TR off

    style sources fill:#fafafa,stroke:#cfcfcf,color:#555
    style vm fill:#fafafa,stroke:#cfcfcf,color:#555
    style storage fill:#fafafa,stroke:#cfcfcf,color:#555
    style offline fill:#fafafa,stroke:#cfcfcf,color:#555,stroke-dasharray:5 4
```

> Day 2's Redis queue is not part of this deployment. Both ingestion containers write directly to RDS and S3 (see ADR-004).

---

## 3. Trade-off analysis

_AirBreda-specific. Reference the ADRs rather than repeating them._

---

## 4. Cloud provider rationale

_Written for a municipal, non-technical audience._

---

## 5. Cost estimate

| Scenario | Monthly cost | Notes |
|---|---|---|
| 10 corridors | | |
| 50 corridors | | |

---

## 6. Reflection

_What would you do differently?_

---

## Architecture Decision Records

- [ADR-001 — Initial Data Storage Strategy](adr/ADR-001-storage-strategy.md)
