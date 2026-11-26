"""AirBreda — Luchtmeetnet NO2 ingestion for station NL10240."""

import requests
import pandas as pd
import os
import psycopg2
from dotenv import load_dotenv
import logging
from log_utils import log_event
import time
from datetime import datetime, timezone
from health import start_health_server

# DESIGN NOTES
# CAP trade-off: the Luchtmeetnet sensor network prefers AVAILABILITY over consistency.
# The API answers immediately with whatever RIVM has validated so far, so readings run around 1 hour behind real time and an offline station is just absent from a HTTP 200 response. 
# A consistency-first design would withhold everything until all stations reported, which  is more correct, but a municipal dashboard would go blank for hours. 
# For this purpose, late data is more useful than no data, that's why AP was chosen here.

# Null / missing values in production: I keep three states distinguishable: no row (never polled), row with NULL value (sensor reported nothing), and row with a real value. 
# Store nulls, never drop the row and never substitute 0.
# Dropping hides an outage, zero-filling invents clean air and would poison model training. 
# Impute downstream where the choice is explicit, and show "no data" rather than 0 in the dashboard.

STATION = "NL10240"
API_URL = f"https://api.luchtmeetnet.nl/open_api/stations/{STATION}/measurements"

load_dotenv()

INSERT_SQL = """
INSERT INTO sensor_readings (station_id, timestamp, component, value, is_flagged)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (station_id, timestamp, component) DO NOTHING;
"""


def fetch_measurements(station: str = STATION, pages: int = 1) -> list[dict]:
    """Fetch raw measurement records, newest first. Returns [] on failure."""
    params = {
        "order_by": "timestamp_measured",
        "order_direction": "desc",
        "page": pages,
    }
    url = f"https://api.luchtmeetnet.nl/open_api/stations/{station}/measurements"

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.Timeout:
        log_event(logging.ERROR, "fetch_failed", source="Luchtmeetnet", reason="timeout")
        return []
    except requests.ConnectionError:
        log_event(logging.ERROR, "fetch_failed", source="Luchtmeetnet", reason="connection")
        return []
    except requests.HTTPError as exc:
        log_event(logging.ERROR, "fetch_failed", source="Luchtmeetnet", reason=f"http_{exc.response.status_code}")
        return []

    return response.json().get("data", [])


def filter_no2_readings(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only NO2 rows. Null values are preserved, not dropped."""
    return df[df["formula"] == "NO2"].copy()

def flag_data_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Flag null values and runs of 3+ identical hourly values."""
    df = df.sort_values("timestamp_measured").copy()
    is_null = df["value"].isna()
    run_id = (df["value"] != df["value"].shift()).cumsum()
    run_len = df.groupby(run_id)["value"].transform("size")
    is_stale = (run_len >= 3) & ~is_null
    df["is_flagged"] = is_null | is_stale
    df["flag_reason"] = None
    df.loc[is_null, "flag_reason"] = "null"
    df.loc[is_stale, "flag_reason"] = "stale"
    return df

def get_latest_no2(df: pd.DataFrame) -> pd.Series | None:
    """Return the newest NO2 row, or None if there are none."""
    no2 = filter_no2_readings(df)
    if no2.empty:
        return None
    return no2.sort_values("timestamp_measured", ascending=False).iloc[0]


def write_readings(df: pd.DataFrame, station: str = STATION) -> int:
    """Insert readings into the database. Returns rows actually inserted."""
    if df.empty:
        return 0

    rows = [
        (
            station,
            r.timestamp_measured,
            r.formula,
            None if pd.isna(r.value) else float(r.value),
            bool(r.is_flagged),
        )
        for r in df.itertuples()
    ]

    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode="require",
        connect_timeout=10,
    )
    try:
        with conn, conn.cursor() as cur:
            cur.executemany(INSERT_SQL, rows)
            return cur.rowcount
    finally:
        conn.close()


if __name__ == "__main__":
    state = {"source": "Luchtmeetnet", "last_successful_fetch": None, "bad_data_count": 0}
    if os.environ.get("HEALTH_PORT"):
        start_health_server(state, int(os.environ["HEALTH_PORT"]))

    records = fetch_measurements()

    if not records:
        log_event(logging.ERROR, "no_data", source="Luchtmeetnet", station_id=STATION)
    else:
        df = pd.DataFrame(records)
        no2 = flag_data_quality(filter_no2_readings(df))

        luchtmeetnet_bad_data_count = 0
        for r in no2[no2["is_flagged"]].itertuples():
            luchtmeetnet_bad_data_count += 1
            log_event(logging.WARNING, "DATA_QUALITY_ERROR", source="Luchtmeetnet",
                      station_id=STATION, field="NO2", reason=r.flag_reason,
                      value=None if pd.isna(r.value) else float(r.value))
        log_event(logging.INFO, "fetch_success", source="Luchtmeetnet",
                  station_id=STATION, rows=len(no2))
        
        state["last_successful_fetch"] = datetime.now(timezone.utc).isoformat()
        state["bad_data_count"] = luchtmeetnet_bad_data_count

        if luchtmeetnet_bad_data_count > 10:
            log_event(logging.ERROR, "BAD_DATA_THRESHOLD_EXCEEDED", source="Luchtmeetnet", count=luchtmeetnet_bad_data_count)

        try:
            inserted = write_readings(no2)
            log_event(logging.INFO, "db_write", inserted=inserted)
        except psycopg2.OperationalError as exc:
            log_event(logging.ERROR, "db_write_failed", error=str(exc))

        latest = get_latest_no2(df)
        if latest is None:
            log_event(logging.WARNING, "no_no2_readings", station_id=STATION)
        else:
            value = None if pd.isna(latest["value"]) else float(latest["value"])
            log_event(logging.INFO, "latest_no2", station_id=STATION,
                      value=value, measured=latest["timestamp_measured"])

    if os.environ.get("HEALTH_PORT"):
        time.sleep(60)  # keep alive so /health can be checked