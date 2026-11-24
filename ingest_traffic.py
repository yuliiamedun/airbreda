"""AirBreda — NDW traffic ingestion for the four A27 sites near Breda.

Parsing helpers reused from getTrafficReadings.py, provided by the course
(BredaUniversityADSAI/Yr3ElectivesStudyMaterial).
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
from datetime import datetime
from pathlib import Path

import boto3
from dotenv import load_dotenv

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


if __name__ == "__main__":
    bucket = os.environ["S3_BUCKET"]
    s3 = boto3.client("s3")

    config_bytes = download_and_decompress(CONFIG_URL).read()
    measured_bytes = download_and_decompress(MEASURED_URL).read()

    for label, site_id in SITES.items():
        summary = report_site(config_bytes, measured_bytes, site_id)

        if summary["timestamp"] is None:
            print(f"No readings for {label}, skipping.")
            continue

        key, path = save_csv(label, summary)
        s3.upload_file(str(path), bucket, key)
        print(f"Uploaded s3://{bucket}/{key}")