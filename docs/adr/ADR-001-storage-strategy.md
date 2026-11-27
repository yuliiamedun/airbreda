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
- **Query flexibility:** I would need to plan the main query patterns in advance. New queries might require additional indexes or full scans.
- **No joins:** comparing air quality and traffic data is one of the main features of the application, and DynamoDB doesn't support joins the way relational databases do.
- **Scalability:** DynamoDB is designed for much larger datasets. With around 130,000 rows per year, I don't need that level of scalability.

## Consequences

- **Easy queries and joins.** Time-range queries and the hourly NO₂–traffic join are simple SQL, which `build_training_data.py` relies on.
- **Safe re-runs.** The composite key with `ON CONFLICT DO NOTHING` makes ingestion idempotent, so a failed or repeated run never creates duplicates. This is also what lets the next hourly run fill gaps after an outage (see ADR-003).
- **Two stores to join.** Because NO₂ lives in the database and traffic lives in S3, the training script has to read both and join them in Python rather than in one SQL query. That is acceptable at this volume, but it is the cost of splitting the data.
- **Raw data is not preserved (known gap).** Since only parsed CSVs are uploaded, the per-lane values, vehicle types and `-1` sentinel speeds in the original XML are lost. This undermines the main reason for using object storage, and it is the decision I would be least confident defending. The fix is to upload the original `.xml.gz` next to each CSV. I see this as a gap in the implementation rather than a deliberate trade-off.
- **Possible future change.** At the current volume, a time-series database such as TimescaleDB would add little over plain PostgreSQL. If the project grew to 50 corridors, I would reconsider this choice.