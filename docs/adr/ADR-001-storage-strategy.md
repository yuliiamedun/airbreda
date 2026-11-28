# ADR-001: Initial Data Storage Strategy

**Status:** Accepted. Implemented, with one known gap (see Consequences).

## Context

AirBreda collects two live data sources: hourly NO₂ readings from RIVM Luchtmeetnet and vehicle counts and speeds from four NDW sites on the A27. Both sources are needed for model training and predictions, and the data should remain available for future retraining.

## Decision

Parsed NO₂ readings go to a managed relational database (AWS RDS for PostgreSQL, `db.t4g.micro`, eu-north-1). Traffic data goes to an S3 bucket.

### 1. Why a relational database instead of NoSQL?
I chose a relational database because our data is already structured in tables, with the same fields for every reading: (station_id, timestamp, component, value). We don't really need the flexibility that NoSQL offers.

Our main queries involve filtering data by time and comparing NO₂ readings with traffic data from the same hour. A relational database handles this well through indexes and joins.

The dataset is also relatively small: around 130,000 rows per year, or 1–2 million over five years. NoSQL would offer flexibility and scalability that I don't currently need.

### 2. Why object storage for the traffic data?
S3 is intended for storing files long-term at a low cost. Keeping the original NDW XML files would also let me recover details lost during processing, such as per-lane counts and vehicle types.

However, the current script uploads only parsed CSV files, not the original XML. This means some information is already lost.

### 3. How do I handle duplicate readings?
The Luchtmeetnet API can return the same reading more than once, for example when polling it multiple times within the same hour.

To prevent duplicates, I use a combination of station_id, timestamp and component as the primary key. With `INSERT ... ON CONFLICT DO NOTHING`, existing readings are simply skipped.

This also makes it safe to rerun the ingestion process if something fails. I don't need a complicated system to guarantee exactly-once delivery.

I also made the value field nullable. This allows me to store a reading even when a sensor doesn't return a value, making it possible to distinguish between a sensor that was checked but returned nothing and one that was never polled.

### 4. Why did I reject DynamoDB?
I considered DynamoDB but rejected it for three reasons:
- I would need to plan the main query patterns in advance. New queries might require additional indexes or full scans.
- Comparing air quality and traffic data is one of the main features of the application, and DynamoDB doesn't support joins the way relational databases do.
- DynamoDB is designed for much larger datasets. With around 130,000 rows per year, I don't need that level of scalability.

## Consequences

- **Easy queries and joins.** PostgreSQL handles time-range queries and hourly NO₂–traffic joins, which build_training_data.py uses.
- **Safe re-runs.** The composite key and ON CONFLICT DO NOTHING prevent duplicates and allow the next run to fill gaps after an outage (see ADR-003).
- **Two stores to join.** Because NO₂ lives in the database and traffic lives in S3, the training script has to read both and join them in Python rather than in one SQL query. That is acceptable at this volume, but it is the cost of splitting the data.
- **Raw data is not preserved (known gap).** Only parsed CSVs are uploaded, so details like per-lane counts, vehicle types and -1 speeds are lost. I should also upload the original .xml.gz files. This is an implementation gap, not an intentional trade-off.
- **Possible future change.** TimescaleDB would add little at the current scale. I would reconsider it if the project grew to 50 corridors for example.