"""
Analytics Engine

Sits between the IoT sensor and the ML model in the flow:

    IoT sensor -> [Analytics Engine] -> ML model -> Alert system

Responsibilities:
    1. Validate incoming raw telemetry (types, ranges, missing fields)
    2. Load the active ML model and get a RUL prediction
    3. Persist the telemetry record (with its prediction) to the DB
    4. Hand off to the alert service if RUL breaches the limit

"""

import joblib
import pandas as pd
from pathlib import Path

import database
from alert_service import check_threshold, raise_alert

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = str(BASE_DIR.parent / "models" / "rul_model.pkl")
FEATURE_COLUMNS = [
    "temperature_c", "vibration_mm_s", "pressure_kpa",
    "coolant_level_pct", "power_draw_kw", "usage_hours_cum",
]
REQUIRED_FIELDS = ["equipment_id", "equipment_type", "cycle"] + FEATURE_COLUMNS

# Reasonable sanity bounds per sensor are used for input validation.
# (Wide bounds on purpose: this is a plausibility check
VALID_RANGES = {
    "temperature_c": (-20, 80),
    "vibration_mm_s": (0, 20),
    "pressure_kpa": (0, 200),
    "coolant_level_pct": (0, 100),
    "power_draw_kw": (0, 100),
    "usage_hours_cum": (0, 100000),
}

RUL_LIMIT = 30  # cycles; below this the alert system is triggered

_model = None  # lazily loaded, cached module-level singleton


def load_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


class ValidationError(Exception):
    """Raised when incoming telemetry fails validation."""
    pass


def validate_telemetry(record: dict) -> None:
    """
    Raises ValidationError if the record is malformed. Returns None on success.
    """
    missing = [f for f in REQUIRED_FIELDS if f not in record]
    if missing:
        raise ValidationError(f"Missing required fields: {missing}")

    if not isinstance(record["cycle"], int) or record["cycle"] <= 0:
        raise ValidationError("cycle must be a positive integer")

    for field, (low, high) in VALID_RANGES.items():
        value = record[field]
        if not isinstance(value, (int, float)):
            raise ValidationError(f"{field} must be numeric")
        if not (low <= value <= high):
            raise ValidationError(
                f"{field}={value} is outside plausible range [{low}, {high}]"
            )


def predict_rul(record: dict) -> float:
    model = load_model()
    row = pd.DataFrame([{col: record[col] for col in FEATURE_COLUMNS}])
    return float(model.predict(row)[0])


def analyse(record: dict) -> dict:
    """
    Full pipeline for one telemetry reading:
    validate -> predict -> persist -> alert if needed.

    Returns a summary dict describing what happened, useful for the
    Flask route to build a response and for tests to assert against.
    """
    validate_telemetry(record)

    predicted_rul = predict_rul(record)
    telemetry_id = database.insert_telemetry(record, predicted_rul=predicted_rul)

    alert_triggered = check_threshold(predicted_rul, RUL_LIMIT)
    maintenance_id = None
    if alert_triggered:
        maintenance_id = raise_alert(
            equipment_id=record["equipment_id"],
            equipment_type=record["equipment_type"],
            telemetry_id=telemetry_id,
            predicted_rul=predicted_rul,
            rul_limit=RUL_LIMIT,
        )

    return {
        "telemetry_id": telemetry_id,
        "predicted_rul": predicted_rul,
        "alert_triggered": alert_triggered,
        "maintenance_id": maintenance_id,
    }