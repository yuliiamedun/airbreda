# ADR-001: Initial Data Storage Strategy

- **Date:** 2026-11-24
- **Decider:** Yuliia Medun

## Context

AirBreda ingests two live sources: hourly NO₂ readings from RIVM Luchtmeetnet station NL10240 (JSON API), and per-minute vehicle counts and speeds from four NDW sites on the A27 (gzipped DATEX II XML). Both must be queryable for model training and prediction serving, and both must remain available for retraining later.

## Decision

Parsed readings go to a managed relational database (AWS RDS for PostgreSQL, `db.t4g.micro`, eu-north-1). Files go to an S3 bucket.

### 1. Why a relational database instead of NoSQL?
I chose a relational database because our data is already structured in tables, with the same fields for every reading: (station_id, timestamp, component, value). We don't really need the flexibility that NoSQL offers.

Our main queries involve filtering data by time and comparing NO₂ readings with traffic data from the same hour. A relational database handles this well through indexes and joins.

We also have a relatively small dataset: around 130,000 rows per year, or 1–2 million over five years. There is no need for a more complex solution to handle this volume.

### 2. Why store raw files in object storage?
I chose object storage because processing the original files means losing some information. For example, the NDW XML files contain per-lane values and vehicle types, while our current processing only keeps total traffic flow and average speed.  
If I need more details in the future, I can always process the original files again. However, I cannot recover that information from an already simplified summary.  
Object storage is also cheaper (around 4 times less per GB than block storage) and is designed for long-term storage. This makes it a good option for keeping raw files that I don't need to access often.

### 3. How do I handle duplicate readings?
The Luchtmeetnet API can return the same reading more than once, for example, when polling it multiple times within the same hour.

To prevent duplicates, I use a combination of station_id, timestamp, and component as a unique identifier. With INSERT ... ON CONFLICT DO NOTHING, existing readings are simply skipped.

This also makes it safe to rerun the ingestion process if something fails. I don't need a complicated system to guarantee exactly-once delivery.

I also made the value field nullable. This allows me to store a reading even when a sensor doesn't return a value, making it possible to distinguish between a sensor that was checked but returned nothing and one that was never polled.

### 4. Why did I reject DynamoDB?
I considered DynamoDB but rejected it for three reasons:
- Query flexibility: I would need to plan the main query patterns in advance. New queries might require additional indexes or full scans.
- No joins: Comparing air quality and traffic data is one of the main features of the application, and DynamoDB doesn't support joins in the same way as relational databases.
- Scalability: DynamoDB is designed for much larger datasets. With around 130,000 rows per year, I don't need that level of scalability.

### 5. Reflection
The decision I would be least confident defending: storing only processed CSV files in S3 instead of the original .xml.gz files.

One of the main reasons for using object storage is to preserve the original data for future processing. However, my current implementation only uploads simplified CSVs, meaning some of that information is already lost. A better approach would be to store both the original XML files and the processed CSVs. I see this as a gap in the current implementation rather than a deliberate trade-off.

Another decision I might revisit is using regular PostgreSQL instead of a time-series database like TimescaleDB. At our current data volume, its extra features wouldn't make much difference. However, if the project expands to 50 corridors, I would reconsider this choice.