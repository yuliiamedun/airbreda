from pathlib import Path

import joblib

from predict import predict

MODEL_PATH = Path(__file__).parent.parent / "model.pkl"


def test_model_loads():
    model = joblib.load(MODEL_PATH)
    assert model is not None


def test_predict_returns_plausible_values():
    result = predict(3000, 18)
    assert isinstance(result["no2_ug_m3_predicted"], float)
    assert 0 <= result["no2_ug_m3_predicted"] <= 200
    assert 0 <= result["no2_exceedance_risk"] <= 1