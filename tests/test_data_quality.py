from unittest.mock import patch

import pandas as pd
from ingest_air import flag_data_quality, write_readings
import getTrafficReadings as g


def test_stale_and_null_readings_are_flagged_not_dropped():
    df = pd.DataFrame({
        "timestamp_measured": [f"2026-01-01T0{h}:00:00+00:00" for h in range(6)],
        "value": [10.0, 20.0, 20.0, 20.0, None, 30.0],
    })

    result = flag_data_quality(df)

    assert len(result) == 6  # nothing dropped
    flagged = result[result["is_flagged"]]
    assert list(flagged["flag_reason"]) == ["stale", "stale", "stale", "null"]

def test_flagged_rows_are_written_with_is_flagged_true(monkeypatch):
    for key in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]:
        monkeypatch.setenv(key, "x")

    df = pd.DataFrame({
        "timestamp_measured": [f"2026-01-01T0{h}:00:00+00:00" for h in range(6)],
        "formula": ["NO2"] * 6,
        "value": [10.0, 20.0, 20.0, 20.0, None, 30.0],
    })

    with patch("ingest_air.psycopg2.connect") as mock_connect:
        cur = mock_connect.return_value.cursor.return_value.__enter__.return_value
        write_readings(flag_data_quality(df))
        rows = cur.executemany.call_args[0][1]

    assert len(rows) == 6  # nothing dropped
    null_row = [r for r in rows if r[3] is None]
    assert len(null_row) == 1 and null_row[0][4] is True
    assert sum(1 for r in rows if r[4]) == 4  # 3 stale + 1 null

def test_ndw_speed_minus_one_is_excluded_and_counted():
    index_map = {
        "0": {"type": "trafficFlow", "vehicle": "anyVehicle"},
        "1": {"type": "trafficSpeed", "vehicle": "anyVehicle"},
    }
    readings = [
        {"index": "0", "type": "TrafficFlow", "value": "60", "timestamp": "2026-01-01T00:00:00Z"},
        {"index": "1", "type": "TrafficSpeed", "value": "-1", "timestamp": "2026-01-01T00:00:00Z"},
    ]

    with patch.object(g, "build_index_map", return_value=index_map), \
         patch.object(g, "extract_measurements", return_value=readings):
        summary = g.report_site(b"", b"", "fake-site")

    assert summary["avg_speed"] is None      # -1 not used as a speed
    assert summary["bad_speed_count"] == 1   # counted, so the warning fires
    assert summary["total_flow"] == 60       # valid flow is kept