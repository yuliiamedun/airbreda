"""Load model.pkl and return predicted NO2 plus exceedance risk."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

THRESHOLD_UG_M3 = 25
STEEPNESS = 0.2

_model = joblib.load(Path(__file__).parent / "model.pkl")


def exceedance_risk(predicted_no2: float,
                    threshold: float = THRESHOLD_UG_M3,
                    steepness: float = STEEPNESS) -> float:
    """Sigmoid centred on the threshold: 0.5 at the threshold, toward 1 above it."""
    return float(1 / (1 + np.exp(-steepness * (predicted_no2 - threshold))))


def predict(total_intensity_veh_per_hr: float, hour_of_day: int) -> dict:
    X = pd.DataFrame(
        [[total_intensity_veh_per_hr, hour_of_day]],
        columns=["total_intensity_veh_per_hr", "hour_of_day"],
        )
    no2 = float(_model.predict(X)[0])
    return {
        "no2_ug_m3_predicted": no2,
        "no2_exceedance_risk": exceedance_risk(no2),
    }