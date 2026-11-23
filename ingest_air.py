"""AirBreda — Luchtmeetnet NO2 ingestion for station NL10240."""

import requests
import pandas as pd

# DESIGN NOTES
# CAP trade-off: the Luchtmeetnet sensor network prefers AVAILABILITY over consistency.
# The API answers immediately with whatever RIVM has validated so far, so readings run around 1 hour behind real time and an offline station is just absent from a HTTP 200 response. 
# A consistency-first design would withhold everything until all stations reported, which  is more correct, but a municipal dashboard would go blank for hours. 
# For this purpose, late data is more useful than no data, so I chose AP here.

# Null / missing values in production: I keep three states distinguishable: no row (never polled), row with NULL value (sensor reported nothing), and row with a real value. 
# Store nulls, never drop the row and never substitute 0.
# Dropping hides an outage, zero-filling invents clean air and would poison model training. 
# Impute downstream where the choice is explicit, and show "no data" rather than 0 in the dashboard.

STATION = "NL10240"
API_URL = f"https://api.luchtmeetnet.nl/open_api/stations/{STATION}/measurements"


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
        print(f"ERROR: request to {station} timed out after 10s")
        return []
    except requests.ConnectionError:
        print(f"ERROR: could not connect to Luchtmeetnet")
        return []
    except requests.HTTPError as exc:
        print(f"ERROR: API returned {exc.response.status_code}")
        return []

    return response.json().get("data", [])


def filter_no2_readings(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only NO2 rows. Null values are preserved, not dropped."""
    return df[df["formula"] == "NO2"].copy()

def get_latest_no2(df: pd.DataFrame) -> pd.Series | None:
    """Return the newest NO2 row, or None if there are none."""
    no2 = filter_no2_readings(df)
    if no2.empty:
        return None
    return no2.sort_values("timestamp_measured", ascending=False).iloc[0]


if __name__ == "__main__":
    records = fetch_measurements()

    if not records:
        print("No data retrieved — check the error above.")
    else:
        latest = get_latest_no2(pd.DataFrame(records))
        if latest is None:
            print(f"No NO2 readings available for station {STATION}.")
        elif pd.isna(latest["value"]):
            print(f"Latest NO2 reading at {latest['timestamp_measured']} is NULL "
                  f"(sensor reported no value).")
        else:
            print(f"Station:   {STATION}")
            print(f"Component: NO2")
            print(f"Value:     {latest['value']} µg/m³")
            print(f"Measured:  {latest['timestamp_measured']}")
