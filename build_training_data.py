"""AirBreda — join NO2 readings with NDW traffic into training_data.csv."""

import io
import os

import boto3
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

STATION = "NL10240"
SITES = ["hrl", "hrr", "vwd", "vwa"]


def load_no2() -> pd.DataFrame:
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
        cur.execute(
            "SELECT timestamp, value FROM sensor_readings "
            "WHERE station_id = %s AND component = 'NO2' AND value IS NOT NULL",
            (STATION,),
        )
        rows = cur.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=["timestamp", "no2_ug_m3"])
    df["hour"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("h")
    return df.groupby("hour", as_index=False)["no2_ug_m3"].mean()


def load_traffic() -> pd.DataFrame:
    bucket = os.environ["S3_BUCKET"]
    s3 = boto3.client("s3")

    frames = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="ndw/"):
        for obj in page.get("Contents", []):
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            frames.append(pd.read_csv(io.BytesIO(body)))

    df = pd.concat(frames, ignore_index=True)
    df["hour"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("h")
    return df.pivot_table(index="hour", columns="label",
                          values="total_flow_vph", aggfunc="mean")


if __name__ == "__main__":
    no2 = load_no2()
    traffic = load_traffic()
    print(f"NO2 hours: {len(no2)} | traffic hours: {len(traffic)}")

    # Only keep hours where all four sites reported
    traffic = traffic.dropna(subset=SITES)
    traffic["total_intensity_veh_per_hr"] = traffic[SITES].sum(axis=1)

    data = no2.merge(
        traffic[["total_intensity_veh_per_hr"]].reset_index(),
        on="hour", how="inner",
    )
    # Amsterdam time, because traffic follows the local clock
    data["hour_of_day"] = data["hour"].dt.tz_convert("Europe/Amsterdam").dt.hour

    data.to_csv("training_data.csv", index=False)
    print(f"Joined rows: {len(data)} -> training_data.csv")
    print(data.head())