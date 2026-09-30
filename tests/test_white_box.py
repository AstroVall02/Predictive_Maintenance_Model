"""
Module 6a: White-Box Test Cases (pytest)
------------------------------------------
White-box testing = we know and deliberately exercise the internal
logic/branches of the code (validation rules, threshold boundaries,
DB side effects), not just the visible input/output behaviour.

Each test uses an isolated temporary SQLite database (via the
`isolated_db` fixture) so these tests never touch or depend on your
real predictive_maintenance.db.

Run from the app/ directory:
    pytest ../tests/test_white_box.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import database
import analytics_engine as ae
from alert_service import check_threshold


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point database.DB_PATH at a fresh temp file for this test only."""
    test_db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", test_db_path)
    database.init_db()
    database.add_technician("Test Tech", "MRI")
    yield test_db_path


def make_record(**overrides):
    """A known-valid MRI telemetry record, with optional field overrides."""
    base = dict(
        equipment_id="MRI-TEST", equipment_type="MRI", cycle=10,
        temperature_c=20.0, vibration_mm_s=1.0, pressure_kpa=100.0,
        coolant_level_pct=90.0, power_draw_kw=30.0, usage_hours_cum=80.0,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------
# 1-5: validate_telemetry branch/boundary coverage
# ---------------------------------------------------------------------
def test_01_valid_record_passes_validation():
    ae.validate_telemetry(make_record())  # should not raise


def test_02_missing_required_field_raises():
    record = make_record()
    del record["vibration_mm_s"]
    with pytest.raises(ae.ValidationError, match="Missing required fields"):
        ae.validate_telemetry(record)


def test_03_non_numeric_field_raises():
    record = make_record(temperature_c="hot")
    with pytest.raises(ae.ValidationError, match="must be numeric"):
        ae.validate_telemetry(record)


def test_04_field_out_of_plausible_range_raises():
    record = make_record(coolant_level_pct=150.0)  # > 100, outside VALID_RANGES
    with pytest.raises(ae.ValidationError, match="outside plausible range"):
        ae.validate_telemetry(record)


def test_05_non_positive_cycle_raises():
    record = make_record(cycle=0)
    with pytest.raises(ae.ValidationError, match="positive integer"):
        ae.validate_telemetry(record)


# ---------------------------------------------------------------------
# 6-8: check_threshold boundary testing (the classic < vs <= vs > case)
# ---------------------------------------------------------------------
def test_06_check_threshold_below_limit_returns_true():
    assert check_threshold(predicted_rul=20, rul_limit=30) is True


def test_07_check_threshold_exactly_at_limit_returns_false():
    # boundary case: equal to the limit should NOT trigger an alert
    assert check_threshold(predicted_rul=30, rul_limit=30) is False


def test_08_check_threshold_above_limit_returns_false():
    assert check_threshold(predicted_rul=45, rul_limit=30) is False


# ---------------------------------------------------------------------
# 9: predict_rul sanity check against the real trained model
# ---------------------------------------------------------------------
def test_09_predict_rul_returns_plausible_float():
    record = make_record()  # near-brand-new equipment
    predicted = ae.predict_rul(record)
    assert isinstance(predicted, float)
    assert predicted > 0  # a fresh unit should not be predicted as already failed


# ---------------------------------------------------------------------
# 10: full pipeline integration - degraded reading -> alert -> technician assigned
# ---------------------------------------------------------------------
def test_10_analyse_degraded_reading_triggers_alert_and_assigns_technician(isolated_db):
    degraded = make_record(
        cycle=280, temperature_c=29.0, vibration_mm_s=5.0,
        pressure_kpa=88.0, coolant_level_pct=60.0,
        power_draw_kw=43.0, usage_hours_cum=2200.0,
    )
    result = ae.analyse(degraded)

    assert result["alert_triggered"] is True
    assert result["maintenance_id"] is not None

    record = database.get_maintenance_by_id(result["maintenance_id"])
    assert record["work_order_status"] == "scheduled"
    assert record["technician_id"] is not None
