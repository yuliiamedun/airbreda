"""One-off: create the sensor_readings table."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DDL = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    station_id  VARCHAR(20)   NOT NULL,
    timestamp   TIMESTAMPTZ   NOT NULL,
    component   VARCHAR(10)   NOT NULL,
    value       FLOAT,
    PRIMARY KEY (station_id, timestamp, component)
);
"""

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    sslmode="require",
    connect_timeout=10,
)

with conn, conn.cursor() as cur:
    cur.execute(DDL)
    print("Table sensor_readings ready.")

conn.close()