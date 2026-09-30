"""
Database Layer

Creates and manages 4 databases as SQLite tables:
    1. telemetry_records   -> raw + analysed sensor readings (IoT sensor -> Analytics engine)
    2. predictive_models   -> metadata about trained ML model versions
    3. maintenance_records -> RUL predictions, alerts, and work orders
    4. technicians         -> technician directory or assignment

Run directly to (re)create the schema:
    python3 database.py
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR.parent / "predictive_maintenance.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS technicians (
    technician_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    specialization    TEXT NOT NULL,      -- e.g. 'MRI', 'CT', 'Ventilator', 'Dialysis', 'General'
    is_available      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS predictive_models (
    model_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    version       TEXT NOT NULL,
    algorithm     TEXT NOT NULL,          -- e.g. 'RandomForestRegressor'
    rmse          REAL,
    mae           REAL,
    r2_score      REAL,
    trained_at    TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS telemetry_records (
    telemetry_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id        TEXT NOT NULL,
    equipment_type      TEXT NOT NULL,
    cycle               INTEGER NOT NULL,
    temperature_c       REAL NOT NULL,
    vibration_mm_s      REAL NOT NULL,
    pressure_kpa        REAL NOT NULL,
    coolant_level_pct   REAL NOT NULL,
    power_draw_kw       REAL NOT NULL,
    usage_hours_cum     REAL NOT NULL,
    predicted_rul       REAL,             -- filled in by the analytics engine / ML model
    recorded_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_records (
    maintenance_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id        TEXT NOT NULL,
    telemetry_id        INTEGER,          -- FK -> telemetry_records, the reading that triggered this
    predicted_rul        REAL NOT NULL,
    rul_limit            REAL NOT NULL,
    alert_triggered      INTEGER NOT NULL DEFAULT 0,
    alert_time            TEXT,
    technician_id        INTEGER,         -- FK -> technicians, who it was assigned to
    work_order_status    TEXT NOT NULL DEFAULT 'none',  -- none / scheduled / in_progress / completed
    work_order_created_at TEXT,
    work_order_completed_at TEXT,
    FOREIGN KEY (telemetry_id) REFERENCES telemetry_records(telemetry_id),
    FOREIGN KEY (technician_id) REFERENCES technicians(technician_id)
);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    print(f"Database initialised -> {DB_PATH}")



# Telemetry records (IoT sensor -> Analytics engine)

def insert_telemetry(record: dict, predicted_rul: float = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO telemetry_records
               (equipment_id, equipment_type, cycle, temperature_c, vibration_mm_s,
                pressure_kpa, coolant_level_pct, power_draw_kw, usage_hours_cum,
                predicted_rul, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["equipment_id"], record["equipment_type"], record["cycle"],
                record["temperature_c"], record["vibration_mm_s"], record["pressure_kpa"],
                record["coolant_level_pct"], record["power_draw_kw"], record["usage_hours_cum"],
                predicted_rul, datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.lastrowid


# Maintenance records (Alert system -> Work order)

def create_maintenance_alert(equipment_id: str, telemetry_id: int,
                              predicted_rul: float, rul_limit: float) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO maintenance_records
               (equipment_id, telemetry_id, predicted_rul, rul_limit,
                alert_triggered, alert_time, work_order_status)
               VALUES (?, ?, ?, ?, 1, ?, 'none')""",
            (equipment_id, telemetry_id, predicted_rul, rul_limit, datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def schedule_work_order(maintenance_id: int, technician_id: int):
    with get_connection() as conn:
        conn.execute(
            """UPDATE maintenance_records
               SET technician_id = ?, work_order_status = 'scheduled',
                   work_order_created_at = ?
               WHERE maintenance_id = ?""",
            (technician_id, datetime.now(timezone.utc).isoformat(), maintenance_id),
        )


def complete_work_order(maintenance_id: int):
    with get_connection() as conn:
        conn.execute(
            """UPDATE maintenance_records
               SET work_order_status = 'completed', work_order_completed_at = ?
               WHERE maintenance_id = ?""",
            (datetime.now(timezone.utc).isoformat(), maintenance_id),
        )


# Technicians

def add_technician(name: str, specialization: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO technicians (name, specialization) VALUES (?, ?)",
            (name, specialization),
        )
        return cur.lastrowid


def get_available_technician(specialization: str):
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM technicians
               WHERE specialization = ? AND is_available = 1
               LIMIT 1""",
            (specialization,),
        ).fetchone()
        return dict(row) if row else None


# Predictive model registry

def register_model(version: str, algorithm: str, rmse: float, mae: float, r2: float):
    with get_connection() as conn:
        conn.execute("UPDATE predictive_models SET is_active = 0")
        conn.execute(
            """INSERT INTO predictive_models
               (version, algorithm, rmse, mae, r2_score, trained_at, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (version, algorithm, rmse, mae, r2, datetime.now(timezone.utc).isoformat()),
        )


# Read/query helpers for the Flask dashboards

def get_all_technicians() -> list:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM technicians").fetchall()
        return [dict(r) for r in rows]


def get_recent_telemetry(limit: int = 20) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM telemetry_records ORDER BY telemetry_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_maintenance_records() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT m.*, t.name AS technician_name
               FROM maintenance_records m
               LEFT JOIN technicians t ON m.technician_id = t.technician_id
               ORDER BY m.maintenance_id DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_maintenance_for_technician(technician_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM maintenance_records
               WHERE technician_id = ? AND work_order_status != 'completed'
               ORDER BY maintenance_id DESC""",
            (technician_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_maintenance_by_id(maintenance_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM maintenance_records WHERE maintenance_id = ?",
            (maintenance_id,),
        ).fetchone()
        return dict(row) if row else None


def get_active_model():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM predictive_models WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


if __name__ == "__main__":
    init_db()

    # hardcoded technician list for now
    seed_techs = [
        ("Asha Patil", "MRI"), ("Ravi Kulkarni", "CT"),
        ("Sneha Joshi", "Ventilator"), ("Aditya Deshpande", "Dialysis"),
    ]
    for name, spec in seed_techs:
        add_technician(name, spec)
    print(f"Seeded {len(seed_techs)} technicians.")