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

    subgraph ingest["EC2 VM · t3.micro · cron every hour"]
        IA["air container<br/>ingest_air.py<br/>fetch · filter NO2 · flag · insert"]
        IT["traffic container<br/>ingest_traffic.py<br/>decode index map · extract 4 sites"]
        IAM["IAM role<br/>airbreda-vm-role"]
    end

    subgraph storage["Storage · AWS eu-north-1"]
        RDS[("RDS PostgreSQL<br/>db.t4g.micro<br/>sensor_readings")]
        S3[("S3 bucket<br/>ndw/YYYY-MM-DD/HH-site.csv")]
    end

    subgraph planned["Planned — Day 4"]
        ML["Regression model<br/>NO2 exceedance risk"]
        API["Dashboard + JSON API<br/>GET / · GET /site/id · GET /health"]
    end

    LMN --> IA
    NDW --> IT
    IA -->|"INSERT ... ON CONFLICT DO NOTHING<br/>port 5432 · security group rule"| RDS
    IT -->|"HTTPS upload"| S3
    IAM -.->|"S3 access, no stored keys"| IT
    RDS -.-> ML
    S3 -.->|"re-parse for retraining"| ML
    ML -.-> API
    RDS -.-> API

    classDef src fill:#e8f0fe,stroke:#3b6fd4,color:#11243e
    classDef ing fill:#fff4e5,stroke:#d98324,color:#3d2607
    classDef sto fill:#e9f6ec,stroke:#2f8f4e,color:#0f2e1b
    classDef fut fill:#f3f0f7,stroke:#8b7bb8,color:#2b2340,stroke-dasharray:4 3

    class LMN,NDW src
    class IA,IT,IAM ing
    class RDS,S3 sto
    class ML,API fut

    style sources fill:#fafafa,stroke:#cfcfcf,color:#555
    style ingest fill:#fafafa,stroke:#cfcfcf,color:#555
    style storage fill:#fafafa,stroke:#cfcfcf,color:#555
    style planned fill:#fafafa,stroke:#cfcfcf,color:#555,stroke-dasharray:5 4
```

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
