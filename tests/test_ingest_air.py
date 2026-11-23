"""Tests for the AirBreda NO2 ingestion script."""

import pandas as pd
import pytest
import requests

import ingest_air
from ingest_air import filter_no2_readings, get_latest_no2


def test_filter_keeps_null_no2_rows():
    """NO2 rows survive filtering even when their value is null."""
    df = pd.DataFrame({
        "formula": ["NO2", "NO2", "PM10"],
        "value": [18.4, None, 22.1],
        "timestamp_measured": [
            "2026-11-23T08:00:00+00:00",
            "2026-11-23T09:00:00+00:00",
            "2026-11-23T08:00:00+00:00",
        ],
    })
    result = filter_no2_readings(df)

    assert len(result) == 2
    assert result["value"].isnull().sum() == 1  # kept, not silently dropped


def test_filter_drops_other_components():
    """Nothing but NO2 comes back."""
    df = pd.DataFrame({
        "formula": ["NO", "NOx", "PM25"],
        "value": [20.75, 60.66, 4.31],
        "timestamp_measured": ["2026-11-23T14:00:00+00:00"] * 3,
    })
    assert filter_no2_readings(df).empty


def test_latest_returns_newest_reading():
    """The newest timestamp wins, regardless of input order."""
    df = pd.DataFrame({
        "formula": ["NO2", "NO2", "NO2"],
        "value": [27.52, 28.68, 22.61],
        "timestamp_measured": [
            "2026-11-23T12:00:00+00:00",
            "2026-11-23T14:00:00+00:00",
            "2026-11-23T13:00:00+00:00",
        ],
    })
    latest = get_latest_no2(df)

    assert latest["value"] == 28.68
    assert latest["timestamp_measured"] == "2026-11-23T14:00:00+00:00"


def test_latest_returns_none_when_no_no2():
    """A station with no NO2 readings yields None, not an exception."""
    df = pd.DataFrame({
        "formula": ["PM10"],
        "value": [22.1],
        "timestamp_measured": ["2026-11-23T14:00:00+00:00"],
    })
    assert get_latest_no2(df) is None


def test_fetch_survives_timeout(monkeypatch):
    """A timed-out request returns an empty list instead of crashing."""
    def fake_get(*args, **kwargs):
        raise requests.Timeout("simulated timeout")

    monkeypatch.setattr(ingest_air.requests, "get", fake_get)
    assert ingest_air.fetch_measurements() == []