# ADR-001 — Initial Data Storage Strategy

- **Status:** Proposed
- **Date:** 2026-11-23
- **Deciders:** _your name_

---

## Context

AirBreda ingests two live streams with very different shapes:

- **Luchtmeetnet NO₂** — one hourly reading per station, small JSON records, stable schema.
- **NDW traffic** — gzipped DATEX II XML refreshed every minute, four sites, per-lane
  flow and speed values, including sentinel values such as `speed = -1`.

Both need to be queryable for model training and for serving predictions, and the raw
payloads need to be retained so the model can be retrained later against data as it
originally arrived.

## Decision

_State the decision in one or two sentences._

## Rationale

### 1. Why a relational database instead of NoSQL

_Consider: fixed schema, low write volume (1 reading/hour/station), the need for
time-range queries and joins between air quality and traffic on timestamp, and
aggregate queries for model features._

### 2. Why raw files are stored in object storage

_Consider: cost per GB, immutability of the raw record, schema evolution, and the fact
that the NDW payload is XML that would have to be reshaped to fit a table._

### 3. How duplicate readings are handled

_Consider: the API returns the same hourly reading on every poll within that hour.
A natural key of (station, formula, timestamp_measured) with a unique constraint and
an upsert (`INSERT ... ON CONFLICT DO NOTHING`) makes ingestion idempotent._

### 4. One alternative considered and rejected

_e.g. DynamoDB, a single S3 data lake with Athena, or TimescaleDB. State why it lost._

## Consequences

**Positive:**

**Negative / accepted costs:**

## Reflection

_Which architectural decision from today would you be least confident defending in a
design review, and why?_
