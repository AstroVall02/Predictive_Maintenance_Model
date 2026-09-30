"""
ML Model Training (Analytics Engine -> ML Model)

Trains a RandomForestRegressor to predict Remaining Useful Life (RUL) 
from telemetry sensor readings, evaluates it, and saves it for the
Flask app to load at inference time.

Split strategy: by equipment_id (group split), NOT random row split.

This matters since random splitting would let the model see cycles from
the same unit in both train and test, which leaks information and
gives an unrealistically good score. Splitting by unit simulates the
real deployment scenario: predicting RUL for equipment the model has
never seen telemetry from before.

Usage:
    python3 ml_model.py                # train + evaluate + save
"""

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = str(BASE_DIR.parent / "data" / "telemetry_dataset.csv")
MODEL_PATH = str(BASE_DIR.parent / "models" / "rul_model.pkl")

FEATURE_COLUMNS = [
    "temperature_c",
    "vibration_mm_s",
    "pressure_kpa",
    "coolant_level_pct",
    "power_draw_kw",
    "usage_hours_cum",
]
TARGET_COLUMN = "RUL"


def load_data(path: str = DATA_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def split_by_equipment(df: pd.DataFrame, test_size: float = 0.2, seed: int = 42):
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train_idx, test_idx = next(splitter.split(df, groups=df["equipment_id"]))
    return df.iloc[train_idx].copy(), df.iloc[test_idx].copy()


def train_model(train_df: pd.DataFrame) -> RandomForestRegressor:
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]

    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model: RandomForestRegressor, test_df: pd.DataFrame) -> dict:
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET_COLUMN]
    preds = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    return {"rmse": rmse, "mae": mae, "r2": r2}


def predict_rul(model: RandomForestRegressor, features: dict) -> float:
    """
    Used by the analytics engine / Flask app at inference time.
    `features` is a dict with the 6 FEATURE_COLUMNS as keys.
    """
    row = pd.DataFrame([features])[FEATURE_COLUMNS]
    return float(model.predict(row)[0])


if __name__ == "__main__":
    df = load_data()
    train_df, test_df = split_by_equipment(df)

    print(f"Train: {len(train_df)} rows from {train_df['equipment_id'].nunique()} units")
    print(f"Test:  {len(test_df)} rows from {test_df['equipment_id'].nunique()} units")

    model = train_model(train_df)
    metrics = evaluate_model(model, test_df)

    print("\nEvaluation on held-out equipment units:")
    print(f"  RMSE: {metrics['rmse']:.2f} cycles")
    print(f"  MAE:  {metrics['mae']:.2f} cycles")
    print(f"  R^2:  {metrics['r2']:.4f}")

    print("\nTop feature importances:")
    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda x: -x[1],
    )
    for name, imp in importances:
        print(f"  {name:20s} {imp:.3f}")

    joblib.dump(model, MODEL_PATH)
    print(f"\nModel saved -> {MODEL_PATH}")

    import database
    database.register_model(
        version="v1.0",
        algorithm="RandomForestRegressor",
        rmse=metrics["rmse"],
        mae=metrics["mae"],
        r2=metrics["r2"],
    )
    print("Model metadata registered in predictive_models table.")