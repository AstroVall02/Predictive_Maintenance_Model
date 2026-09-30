"""
Module 1: Synthetic Telemetry Data Generator
----------------------------------------------
Simulates run-to-failure telemetry for heavy medical equipment
(MRI Scanners, CT Scanners, Ventilators, Dialysis Machines).

Each unit runs for a random number of operating cycles before failure.
Sensor readings drift as the unit approaches failure (mirrors real
degradation patterns), with noise added for realism.

Output: data/telemetry_dataset.csv
Columns:
    equipment_id      - unique id per physical unit
    equipment_type     - MRI / CT / Ventilator / Dialysis
    cycle               - operating cycle number (like a day of use)
    temperature_c       - core operating temperature
    vibration_mm_s       - vibration amplitude
    pressure_kpa        - internal pressure (coolant/air/hydraulic)
    coolant_level_pct   - coolant/fluid level percentage
    power_draw_kw        - power drawn during cycle
    usage_hours_cum     - cumulative usage hours
    RUL                  - Remaining Useful Life (cycles until failure) -- LABEL
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

EQUIPMENT_TYPES = {
    # type: (baseline temp, baseline vibration, baseline pressure, baseline coolant, baseline power)
    "MRI":       dict(temp=18.0, vib=0.8, pres=101.0, coolant=95.0, power=35.0),
    "CT":        dict(temp=24.0, vib=1.2, pres=98.0,  coolant=90.0, power=28.0),
    "Ventilator":dict(temp=32.0, vib=0.3, pres=20.0,  coolant=100.0, power=0.6),
    "Dialysis":  dict(temp=29.0, vib=0.5, pres=45.0,  coolant=85.0, power=1.5),
}

N_UNITS_PER_TYPE = 25          # number of physical units simulated per equipment type
MIN_LIFE, MAX_LIFE = 120, 300  # operating cycles before failure


def simulate_unit(equipment_id: int, equipment_type: str) -> pd.DataFrame:
    base = EQUIPMENT_TYPES[equipment_type]
    life = RNG.integers(MIN_LIFE, MAX_LIFE)
    cycles = np.arange(1, life + 1)

    # degradation fraction: 0 at start, 1 at failure (non-linear, accelerates near end)
    frac = (cycles / life) ** 2.5

    noise = lambda scale: RNG.normal(0, scale, size=life)

    temperature = base["temp"] + frac * RNG.uniform(6, 12) + noise(0.4)
    vibration = base["vib"] + frac * RNG.uniform(2.5, 4.5) + noise(0.05)
    pressure = base["pres"] - frac * RNG.uniform(8, 15) + noise(0.6)
    coolant = base["coolant"] - frac * RNG.uniform(20, 35) + noise(1.0)
    power = base["power"] + frac * RNG.uniform(4, 9) + noise(0.3)
    usage_hours_cum = cycles * RNG.uniform(6, 10)

    rul = life - cycles  # 0 at the last recorded cycle (failure point)

    return pd.DataFrame({
        "equipment_id": f"{equipment_type}-{equipment_id:03d}",
        "equipment_type": equipment_type,
        "cycle": cycles,
        "temperature_c": temperature.round(2),
        "vibration_mm_s": vibration.round(3),
        "pressure_kpa": pressure.round(2),
        "coolant_level_pct": coolant.clip(0, 100).round(2),
        "power_draw_kw": power.round(3),
        "usage_hours_cum": usage_hours_cum.round(1),
        "RUL": rul,
    })


def generate_dataset() -> pd.DataFrame:
    frames = []
    for etype in EQUIPMENT_TYPES:
        for uid in range(1, N_UNITS_PER_TYPE + 1):
            frames.append(simulate_unit(uid, etype))
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    df = generate_dataset()
    out_path = "telemetry_dataset.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} telemetry records across "
          f"{df['equipment_id'].nunique()} units -> {out_path}")
    print(df.head())
