# Predictive Maintenance ML Model for Heavy Medical Infrastructure

A full-stack predictive maintenance system for heavy medical equipment (MRI scanners, CT scanners, ventilators, dialysis machines). IoT-simulated telemetry is analysed by a machine learning model to predict **Remaining Useful Life (RUL)**; when predicted RUL drops below a safety threshold, the system automatically raises an alert and schedules a work order with an available technician.

Built for the **Software Engineering and Modelling (SEM)** course.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [System Actors](#system-actors)
- [System Flow](#system-flow)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Dataset](#dataset)
- [Machine Learning Model](#machine-learning-model)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Software Engineering Artifacts](#software-engineering-artifacts)
- [Future Improvements](#future-improvements)

---

## Problem Statement

Heavy medical equipment (MRI, CT, ventilators, dialysis machines) is safety-critical and expensive to replace or repair reactively. This project builds a predictive maintenance pipeline that continuously monitors equipment telemetry, predicts how many operating cycles remain before failure, and proactively schedules maintenance before a breakdown occurs — reducing unplanned downtime and improving patient safety.

## System Actors

| Actor | Role |
|---|---|
| **Heavy Medical Equipment** | Source of telemetry (simulated via the IoT Engineer's dashboard) |
| **IoT Engineer** | Registers/simulates equipment sensor readings |
| **Hospital Technician** | Receives alerts, manages and completes work orders |
| **Biomedical Manager** | Monitors fleet-wide equipment health and model performance |

## System Flow

```
1. IoT sensor reads raw telemetry data and transmits it
        │
        ▼
2. Analytics Engine receives and validates the data
        │
        ▼
3. Data is fed into the ML Model → predicts Remaining Useful Life (RUL)
        │
        ▼
4. If RUL < Limit → Alert Notification System notifies technician,
   who is auto-assigned a work order
        │
        ▼
5. Data is updated into the respective databases
        │
        ▼
6. Repeat
```

## Architecture

**Databases** (implemented as SQLite tables):
1. `telemetry_records` — raw + analysed sensor readings
2. `maintenance_records` — RUL predictions, alerts, work order status
3. `predictive_models` — trained model version metadata & metrics
4. `technicians` — technician directory and specialization

**Modules:**
- `generate_data.py` — synthetic run-to-failure telemetry generator (IoT sensor simulation)
- `ml_model.py` — trains, evaluates, and registers the RUL prediction model
- `database.py` — schema definitions and all DB read/write operations
- `analytics_engine.py` — validates telemetry, orchestrates prediction, persists records
- `alert_service.py` — threshold check, alert creation, auto-technician-assignment
- `app.py` — Flask web application (role-based login + 3 dashboards)

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask |
| Database | SQLite |
| ML | scikit-learn (RandomForestRegressor) |
| Frontend | Jinja2 templates + Bootstrap 5 |
| White-box testing | pytest |
| Black-box testing | Selenium |

## Project Structure

```
predictive-maintenance/
├── predictive_maintenance.db       
├── requirements.txt
├── .gitignore
├── README.md
├── data/
│   ├── generate_data.py           
│   └── telemetry_dataset.csv      
├── models/
│   └── rul_model.pkl               
├── app/
│   ├── app.py                      
│   ├── ml_model.py                 
│   ├── database.py                 
│   ├── analytics_engine.py         
│   ├── alert_service.py            
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── iot_dashboard.html
│   │   ├── technician_dashboard.html
│   │   └── manager_dashboard.html
│   └── static/
└── tests/
    ├── test_white_box.py           
    └── test_black_box.py  
```

## Dataset

No public telemetry dataset exists for heavy medical equipment run-to-failure data — hospital biomedical sensor logs are proprietary and not released publicly (unlike, e.g., NASA's C-MAPSS turbofan engine dataset, which is the standard RUL benchmark for industrial equipment).

`data/generate_data.py` therefore synthesizes a physics-informed dataset: 100 simulated units (25 each of MRI, CT, Ventilator, Dialysis) are run to failure over 120–300 cycles, with sensor readings (temperature, vibration, pressure, coolant level, power draw) drifting along a **non-linear degradation curve** that accelerates near failure — the same principle used in standard Prognostics and Health Management (PHM) benchmarks. This produces 20,240 labelled telemetry records with a ground-truth RUL for each reading.

## Machine Learning Model

- **Algorithm:** RandomForestRegressor (scikit-learn)
- **Features:** temperature, vibration, pressure, coolant level, power draw, cumulative usage hours
- **Target:** Remaining Useful Life (RUL), in cycles
- **Validation strategy:** split by `equipment_id` (not by row) — the model is evaluated only on equipment units it has never seen telemetry from, simulating real deployment
- **Performance on held-out units:**

  | Metric | Value |
  |---|---|
  | RMSE | ~31 cycles |
  | MAE | ~22 cycles |
  | R² | ~0.80 |

  Vibration is the dominant predictive feature (~77% importance).

## Setup & Installation

Requires Python 3.10+ and (for black-box tests) Google Chrome installed.

```bash
git clone <your-repo-url>
cd predictive-maintenance

# create and activate a virtual environment (uv recommended)
uv venv
source .venv/bin/activate

# install dependencies
uv pip install -r requirements.txt
```

> Using plain `pip` instead of `uv`? Replace the last command with:
> `pip install -r requirements.txt`

## Running the Application

### Option 1: One-Click Run (Windows)
Simply double-click [`run.bat`](file:///c:/Users/Abhinandan%20Singh/Desktop/COLLEGE%20STUFF/4SEM/miniproj/Predictive_Maintenance_Model/run.bat) or run from terminal:
```cmd
run.bat
```
*(This automatically checks your virtual environment, dependencies, dataset/model/db prerequisites, starts Flask, and opens `http://127.0.0.1:5000` in your browser).*

### Option 2: Manual Run
Run these **in order** from the `app/` directory — each step generates a file the next one depends on:

```bash
cd app

python3 ../data/generate_data.py   # 1. generate synthetic telemetry data
python3 ml_model.py                # 2. train model, save to models/, register metrics
python3 database.py                # 3. create DB schema + seed technicians
python3 app.py                     # 4. start the Flask server
```

Then open **http://127.0.0.1:5000** in a browser.

**Demo credentials:**

| Role | Username | Password |
|---|---|---|
| IoT Engineer | `iot_engineer` | `iot123` |
| Biomedical Manager | `manager` | `mgr123` |
| Technician | *(select name from dropdown on the login page)* | — |

## Testing

### White-box tests (pytest)

10 test cases covering input validation branches, RUL-threshold boundaries, and the full analyse→alert→schedule pipeline, using an isolated temporary database:

- **Windows batch runner**: Double-click [`test_whitebox.bat`](file:///c:/Users/Abhinandan%20Singh/Desktop/COLLEGE%20STUFF/4SEM/miniproj/Predictive_Maintenance_Model/test_whitebox.bat) or run:
  ```cmd
  test_whitebox.bat
  ```
- **Manual command**:
  ```bash
  cd app
  pytest ../tests/test_white_box.py -v
  ```

### Black-box tests (Selenium)

10 test cases driving the real application through a browser — login (valid/invalid/role-restricted), submitting healthy/degraded readings and verifying the resulting alert UI, and a technician completing a work order end-to-end.

- **Windows batch runner** (automatically starts background Flask server if not already running):
  Double-click [`test_blackbox.bat`](file:///c:/Users/Abhinandan%20Singh/Desktop/COLLEGE%20STUFF/4SEM/miniproj/Predictive_Maintenance_Model/test_blackbox.bat) or run:
  ```cmd
  test_blackbox.bat
  ```
- **Manual command**:
  ```bash
  # Terminal 1 — keep the app running
  cd app && python3 app.py

  # Terminal 2
  pytest tests/test_black_box.py -v
  ```

Selenium 4.6+ auto-manages the matching ChromeDriver — no manual driver install needed, as long as Chrome is installed.

## Software Engineering Artifacts

The following design artifacts were produced prior to implementation (included separately in the course submission, not in this repository):
- Functional & Non-Functional Requirements
- Data Flow Diagrams (Level 0, 1, 2)
- Use Case Diagram
- Sequence Diagram
- Activity Diagram
- Class Diagram
- Project estimation: Function Point Analysis, COCOMO II, PERT

## Future Improvements

- Replace demo credentials with a proper authentication/authorization system
- Add a scheduler (e.g. APScheduler) to auto-generate telemetry on an interval instead of manual form submission
- Retrain on real hospital biomedical sensor data if/when available
- Add model versioning/rollback and periodic retraining pipeline
