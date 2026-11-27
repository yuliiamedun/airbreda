"""Dashboard and API (step 1: /site/{site_id})."""

import csv
import io
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import json

import boto3
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

import logging
from log_utils import log_event

from predict import predict

load_dotenv()

STATION = "NL10240"
SITES = ["hrl", "hrr", "vwd", "vwa"]
BUCKET = os.environ["S3_BUCKET"]

app = FastAPI()
s3 = boto3.client("s3")


def latest_no2():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], sslmode="require", connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM sensor_readings "
                "WHERE station_id = %s AND component = 'NO2' AND value IS NOT NULL "
                "ORDER BY timestamp DESC LIMIT 1",
                (STATION,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def latest_traffic(site: str):
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="ndw/"):
        keys += [o["Key"] for o in page.get("Contents", [])
                 if o["Key"].endswith(f"-{site}.csv")]
    if not keys:
        return None
    body = s3.get_object(Bucket=BUCKET, Key=max(keys))["Body"].read().decode("utf-8")
    row = next(csv.DictReader(io.StringIO(body)))
    return float(row["total_flow_vph"]), row["timestamp"]

def get_conn():
    return psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], sslmode="require", connect_timeout=10,
    )


def air_health() -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(timestamp), COUNT(*) FILTER (WHERE is_flagged) "
                "FROM sensor_readings WHERE station_id = %s AND component = 'NO2'",
                (STATION,),
            )
            last, bad = cur.fetchone()
    finally:
        conn.close()
    return {"last_successful_fetch": last.isoformat() if last else None,
            "bad_data_count": bad}


def ndw_health() -> dict:
    last = None
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="ndw/"):
        for o in page.get("Contents", []):
            if last is None or o["LastModified"] > last:
                last = o["LastModified"]
    try:
        body = s3.get_object(Bucket=BUCKET, Key="health/ndw.json")["Body"].read()
        bad = json.loads(body)["bad_data_count"]
    except s3.exceptions.NoSuchKey:
        bad = 0
    return {"last_successful_fetch": last.isoformat() if last else None,
            "bad_data_count": bad}


@app.get("/site/{site_id}")
def site(site_id: str):
    # Where each field comes from:
    #   no2_ug_m3            -> latest NO2 row in RDS sensor_readings (station NL10240)
    #   intensity_veh_per_hr -> latest CSV for this site in the S3 bucket
    #   timestamp            -> timestamp inside that CSV (NDW measurement time)
    #   no2_ug_m3_predicted, no2_exceedance_risk -> predict() from predict.py
    # If predict() raises, the route does NOT fail: it still returns the real
    # NO2 and intensity, with the two prediction fields set to null.
    if site_id not in SITES:
        raise HTTPException(status_code=404, detail="Unknown site")

    try:
        no2 = latest_no2()
        readings = {s: latest_traffic(s) for s in SITES}
    except Exception as exc:
        log_event(logging.ERROR, "data_read_failed", site=site_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Data source unavailable")
    if no2 is None or any(r is None for r in readings.values()):
        log_event(logging.WARNING, "no_data", site=site_id)
        raise HTTPException(status_code=503, detail="No data yet")

    intensity, ts = readings[site_id]
    # The model was trained on the TOTAL of all four sites, so predict with the total
    total = sum(r[0] for r in readings.values())
    hour = (datetime.fromisoformat(ts.replace("Z", "+00:00"))
            .astimezone(ZoneInfo("Europe/Amsterdam")).hour)

    try:
        pred = predict(total, hour)
    except Exception as exc:
        log_event(logging.ERROR, "predict_failed", site=site_id, error=str(exc))
        pred = {"no2_ug_m3_predicted": None, "no2_exceedance_risk": None}
    else:
        log_event(logging.INFO, "site_served", site=site_id,
                  no2=no2, predicted=pred["no2_ug_m3_predicted"])

    return {
        "site_id": site_id,
        "no2_ug_m3": no2,
        "intensity_veh_per_hr": intensity,
        "no2_ug_m3_predicted": pred["no2_ug_m3_predicted"],
        "no2_exceedance_risk": pred["no2_exceedance_risk"],
        "timestamp": ts,
    }


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AirBreda</title>
<style>
  :root{--bg:#f4f6f8;--card:#fff;--text:#1d2733;--muted:#6b7785;--line:#e3e8ee}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
  main{max-width:760px;margin:0 auto;padding:2rem 1rem}
  h1{margin:0 0 .25rem;font-size:1.6rem}
  .sub{color:var(--muted);margin:0 0 1.5rem}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1.5rem}
  .card,.tablewrap{background:var(--card);border:1px solid var(--line);border-radius:12px}
  .card{padding:1rem 1.25rem}
  .label{color:var(--muted);font-size:.85rem}
  .value{font-size:2rem;font-weight:700;margin-top:.25rem}
  .unit{font-size:.9rem;font-weight:400;color:var(--muted)}
  .tablewrap{overflow:hidden}
  table{width:100%;border-collapse:collapse}
  th,td{padding:.75rem 1rem;text-align:left;border-bottom:1px solid var(--line)}
  th{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
  tr:last-child td{border-bottom:0}
  .badge{display:inline-block;padding:.15rem .6rem;border-radius:999px;font-weight:600;font-size:.85rem}
  .low{background:#dff5e3;color:#1b6b34}
  .mid{background:#fff1d1;color:#8a5a00}
  .high{background:#fde0e0;color:#a11}
  .foot{color:var(--muted);font-size:.85rem;margin-top:1rem}
  #error{color:#b00}
</style></head>
<body><main>
<h1>AirBreda</h1>
<p class="sub">NO₂ and traffic at the A27 / Breda interchange</p>

<div class="cards">
  <div class="card"><div class="label">Actual NO₂</div>
    <div class="value"><span id="actual">…</span> <span class="unit">µg/m³</span></div></div>
  <div class="card"><div class="label">Predicted NO₂</div>
    <div class="value"><span id="predicted">…</span> <span class="unit">µg/m³</span></div></div>
  <div class="card"><div class="label">Total traffic</div>
    <div class="value"><span id="total">…</span> <span class="unit">veh/hr</span></div></div>
</div>

<div class="tablewrap"><table>
  <thead><tr><th>Site</th><th>Traffic (veh/hr)</th><th>Predicted NO₂</th><th>Exceedance risk</th></tr></thead>
  <tbody id="rows"></tbody>
</table></div>

<p class="foot">Traffic measured: <span id="updated">…</span></p>
<p id="error"></p>

<script>
const sites = ["hrl", "hrr", "vwd", "vwa"];
const fmt = (v, d) => (v === null || v === undefined) ? "n/a" : v.toFixed(d);
const riskClass = r => r === null ? "" : r < 0.33 ? "low" : r < 0.66 ? "mid" : "high";

Promise.all(sites.map(s =>
  fetch("/site/" + s).then(r => {
    if (!r.ok) throw new Error("/site/" + s + " returned " + r.status);
    return r.json();
  })
)).then(data => {
  document.getElementById("actual").textContent = fmt(data[0].no2_ug_m3, 1);
  document.getElementById("predicted").textContent = fmt(data[0].no2_ug_m3_predicted, 1);
  document.getElementById("total").textContent = data.reduce((a, d) => a + d.intensity_veh_per_hr, 0);
  document.getElementById("updated").textContent = new Date(data[0].timestamp).toLocaleString();
  document.getElementById("rows").innerHTML = data.map(d =>
    "<tr><td><b>" + d.site_id + "</b></td><td>" + d.intensity_veh_per_hr +
    "</td><td>" + fmt(d.no2_ug_m3_predicted, 1) +
    '</td><td><span class="badge ' + riskClass(d.no2_exceedance_risk) + '">' +
    fmt(d.no2_exceedance_risk, 2) + "</span></td></tr>"
  ).join("");
}).catch(e => { document.getElementById("error").textContent = e.message; });
</script>
</main></body></html>"""


@app.get("/health")
def health():
    result = {"status": "ok"}
    for name, fn in (("luchtmeetnet", air_health), ("ndw", ndw_health)):
        try:
            result[name] = fn()
        except Exception as exc:
            log_event(logging.ERROR, "health_check_failed", source=name, error=str(exc))
            result["status"] = "degraded"
            result[name] = {"last_successful_fetch": None,
                            "bad_data_count": None, "error": str(exc)}
    return result

@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE