"""
Flask Application

Web interface:
    - IoT Engineer          : simulate/submit telemetry readings
    - Hospital Technician   : view alerts assigned to them, complete work orders
    - Biomedical Manager    : fleet-wide dashboard + model performance

Run:
    python3 app.py
    -> open http://127.0.0.1:5000
"""

from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for

import database
from analytics_engine import RUL_LIMIT, ValidationError, analyse

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"

EQUIPMENT_TYPES = ["MRI", "CT", "Ventilator", "Dialysis"]

# Demo credentials for the non-technician roles. Technicians log in by
# picking their name from the seeded technicians table instead (no
# separate password), since they're already first-class records in the DB.
DEMO_USERS = {
    "iot_engineer": {"password": "iot123", "role": "iot_engineer", "label": "IoT Engineer"},
    "manager": {"password": "mgr123", "role": "manager", "label": "Biomedical Manager"},
}


# Auth helpers

def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "role" not in session:
                return redirect(url_for("login"))
            if role is not None and session["role"] != role:
                flash("You don't have access to that page.", "error")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.route("/")
def index():
    if "role" not in session:
        return redirect(url_for("login"))
    return redirect(url_for(f"{session['role']}_dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    technicians = database.get_all_technicians()

    if request.method == "POST":
        login_type = request.form.get("login_type")

        if login_type == "technician":
            technician_id = request.form.get("technician_id")
            match = next(
                (t for t in technicians if str(t["technician_id"]) == technician_id),
                None,
            )
            if match:
                session["role"] = "technician"
                session["technician_id"] = match["technician_id"]
                session["display_name"] = match["name"]
                return redirect(url_for("technician_dashboard"))
            flash("Please select a valid technician.", "error")

        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            user = DEMO_USERS.get(username)
            if user and user["password"] == password:
                session["role"] = user["role"]
                session["display_name"] = user["label"]
                return redirect(url_for(f"{user['role']}_dashboard"))
            flash("Invalid username or password.", "error")

    return render_template("login.html", technicians=technicians)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# IoT Engineer dashboard

@app.route("/iot/dashboard")
@login_required("iot_engineer")
def iot_engineer_dashboard():
    recent = database.get_recent_telemetry(limit=15)
    return render_template(
        "iot_dashboard.html",
        equipment_types=EQUIPMENT_TYPES,
        recent=recent,
        rul_limit=RUL_LIMIT,
    )


@app.route("/iot/simulate", methods=["POST"])
@login_required("iot_engineer")
def iot_simulate():
    try:
        record = {
            "equipment_id": request.form["equipment_id"].strip(),
            "equipment_type": request.form["equipment_type"],
            "cycle": int(request.form["cycle"]),
            "temperature_c": float(request.form["temperature_c"]),
            "vibration_mm_s": float(request.form["vibration_mm_s"]),
            "pressure_kpa": float(request.form["pressure_kpa"]),
            "coolant_level_pct": float(request.form["coolant_level_pct"]),
            "power_draw_kw": float(request.form["power_draw_kw"]),
            "usage_hours_cum": float(request.form["usage_hours_cum"]),
        }
        result = analyse(record)
        if result["alert_triggered"]:
            flash(
                f"ALERT: predicted RUL {result['predicted_rul']:.1f} cycles "
                f"(below limit of {RUL_LIMIT}). Work order auto-scheduled.",
                "alert",
            )
        else:
            flash(
                f"Reading recorded. Predicted RUL: {result['predicted_rul']:.1f} cycles. "
                "No alert needed.",
                "success",
            )
    except (ValidationError, KeyError, ValueError) as e:
        flash(f"Invalid telemetry submission: {e}", "error")

    return redirect(url_for("iot_engineer_dashboard"))


# Technician dashboard

@app.route("/technician/dashboard")
@login_required("technician")
def technician_dashboard():
    assigned = database.get_maintenance_for_technician(session["technician_id"])
    return render_template("technician_dashboard.html", assigned=assigned)


@app.route("/technician/complete/<int:maintenance_id>", methods=["POST"])
@login_required("technician")
def complete_work_order(maintenance_id):
    record = database.get_maintenance_by_id(maintenance_id)
    if record is None or record["technician_id"] != session["technician_id"]:
        flash("Work order not found or not assigned to you.", "error")
    else:
        database.complete_work_order(maintenance_id)
        flash(f"Work order #{maintenance_id} marked complete.", "success")
    return redirect(url_for("technician_dashboard"))


# Biomedical Manager dashboard

@app.route("/manager/dashboard")
@login_required("manager")
def manager_dashboard():
    maintenance = database.get_all_maintenance_records()
    telemetry = database.get_recent_telemetry(limit=25)
    model_info = database.get_active_model()
    return render_template(
        "manager_dashboard.html",
        maintenance=maintenance,
        telemetry=telemetry,
        model_info=model_info,
    )


if __name__ == "__main__":
    app.run(debug=True)
