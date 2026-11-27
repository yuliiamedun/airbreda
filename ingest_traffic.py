"""NDW traffic ingestion for the four A27 sites near Breda.

Parsing helpers reused from getTrafficReadings.py, provided by the course (BredaUniversityADSAI/Yr3ElectivesStudyMaterial).
"""

# Why both the database and the bucket:
# The database makes it easy to search and work with the data. 
# For example, we can quickly find NO2 values between two timestamps and compare them with traffic data from the same hours. 
# Doing this with files in the bucket would mean downloading and reading them one by one.

# The bucket stores the original data, so we don't lose information. 
# When we convert the raw XML files into CSVs, we only keep what our current model needs, like total traffic flow and average speed. 
# But the original XML files also contain details like traffic per lane, vehicle types, and -1 values.
#If we need those details in the future, we can always process the original files again. We can't recover that information from the database once we've simplified it.

# Known limitation: this script writes only the parsed CSV, not the original .xml.gz. A complete design would archive the raw payload too.

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
import time
from health import start_health_server
import json

import boto3
from dotenv import load_dotenv

import logging
from log_utils import log_event

from getTrafficReadings import (
    CONFIG_URL,
    MEASURED_URL,
    download_and_decompress,
    report_site,
)

load_dotenv()

SITES = {
    "hrl": "RWS01_MONIBAS_0271hrl0063ra",
    "hrr": "RWS01_MONIBAS_0271hrr0063ra",
    "vwd": "RWS01_MONIBAS_0270vwd0063ra",
    "vwa": "RWS01_MONIBAS_0270vwa0063ra",
}


def save_csv(label: str, summary: dict) -> tuple[str, Path]:
    """Write one site's reading to ndw/YYYY-MM-DD/HH-label.csv."""
    ts = datetime.fromisoformat(summary["timestamp"].replace("Z", "+00:00"))
    key = f"ndw/{ts:%Y-%m-%d}/{ts:%H}-{label}.csv"

    path = Path(key)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["label", "site_id", "timestamp",
                         "total_flow_vph", "avg_speed_kmh"])
        writer.writerow([
            label,
            summary["site_id"],
            summary["timestamp"],
            f"{summary['total_flow']:.0f}",
            "" if summary["avg_speed"] is None else f"{summary['avg_speed']:.1f}",
        ])

    return key, path


HEALTH_KEY = "health/ndw.json"


def save_bad_data_total(s3, bucket: str, bad_this_run: int) -> int:
    """Keep a running total of dropped NDW readings in the bucket, so /health can read it."""
    try:
        body = s3.get_object(Bucket=bucket, Key=HEALTH_KEY)["Body"].read()
        total = json.loads(body)["bad_data_count"]
    except s3.exceptions.NoSuchKey:
        total = 0
    total += bad_this_run
    s3.put_object(Bucket=bucket, Key=HEALTH_KEY,
                  Body=json.dumps({"bad_data_count": total}).encode(),
                  ContentType="application/json")
    return total


if __name__ == "__main__":
    bucket = os.environ["S3_BUCKET"]
    s3 = boto3.client("s3")

    state = {"source": "NDW", "last_successful_fetch": None, "bad_data_count": 0}
    if os.environ.get("HEALTH_PORT"):
        start_health_server(state, int(os.environ["HEALTH_PORT"]))

    try:
        config_bytes = download_and_decompress(CONFIG_URL).read()
        measured_bytes = download_and_decompress(MEASURED_URL).read()
    except Exception as exc:
        log_event(logging.ERROR, "fetch_failed", source="NDW", error=str(exc))
        raise SystemExit(1)

    ndw_bad_data_count = 0

    for label, site_id in SITES.items():
        try:
            summary = report_site(config_bytes, measured_bytes, site_id)

            if summary["bad_speed_count"]:
                ndw_bad_data_count += summary["bad_speed_count"]
                log_event(logging.WARNING, "DATA_QUALITY_ERROR", source="NDW",
                        location=site_id, field="speed", value=-1,
                        count=summary["bad_speed_count"])

            if summary["timestamp"] is None:
                log_event(logging.WARNING, "no_readings", source="NDW", site=label)
                continue

            key, path = save_csv(label, summary)
            s3.upload_file(str(path), bucket, key)
            log_event(logging.INFO, "fetch_success", source="NDW", site=label,
                      timestamp=summary["timestamp"], total_flow=summary["total_flow"])
            log_event(logging.INFO, "s3_upload", key=key)
            state["last_successful_fetch"] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            log_event(logging.ERROR, "site_failed", source="NDW", site=label, error=str(exc))

    state["bad_data_count"] = ndw_bad_data_count
    try:
        save_bad_data_total(s3, bucket, ndw_bad_data_count)
    except Exception as exc:
        log_event(logging.ERROR, "health_save_failed", source="NDW", error=str(exc))
    if ndw_bad_data_count > 10:
        log_event(logging.ERROR, "BAD_DATA_THRESHOLD_EXCEEDED", source="NDW", count=ndw_bad_data_count)

    if os.environ.get("HEALTH_PORT"):
        time.sleep(60)  # keep alive so /health can be checked