"""
Alert Notification System

Responsibilities:
    1. Decide whether a predicted RUL breaches the limit (check_threshold)
    2. If so, create a maintenance_records row (the "alert") in the DB
    3. Auto-assign an available technician matching the equipment type
       and mark a work order as scheduled

"""

import database


def check_threshold(predicted_rul: float, rul_limit: float) -> bool:
    """
    Returns True if an alert should be raised.
    Boundary rule: RUL strictly less than the limit triggers an alert;
    RUL == limit does NOT (equipment is still considered within safe life).
    """
    return predicted_rul < rul_limit


def raise_alert(equipment_id: str, equipment_type: str, telemetry_id: int,
                 predicted_rul: float, rul_limit: float) -> int:
    """
    Creates the maintenance/alert record and attempts to auto-schedule
    a work order with an available technician of the matching specialization.
    Returns the new maintenance_id.
    """
    maintenance_id = database.create_maintenance_alert(
        equipment_id=equipment_id,
        telemetry_id=telemetry_id,
        predicted_rul=predicted_rul,
        rul_limit=rul_limit,
    )

    technician = database.get_available_technician(equipment_type)
    if technician is not None:
        database.schedule_work_order(maintenance_id, technician["technician_id"])

    return maintenance_id
