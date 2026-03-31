"""
SVR Model — Historical Time-Based Congestion Forecaster
Purpose: Predicts expected congestion level based on TIME patterns only
(hour of day, day of week, month) — completely independent of live route data.
"""
import os
import numpy as np
import pandas as pd
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
MODEL_PATH = "svr_model.pkl"

FEATURE_COLS = ["hour","weekday","is_weekend","month","is_peak_am","is_peak_pm","is_night"]
TARGET_COL = "historical_congestion"

def generate_historical_data(n_samples=300):
    np.random.seed(42)
    records = []
    for _ in range(n_samples):
        hour = np.random.randint(0, 24)
        weekday = np.random.randint(0, 7)
        month = np.random.randint(1, 13)
        is_weekend = 1 if weekday >= 5 else 0
        is_peak_am = 1 if 8 <= hour <= 10 else 0
        is_peak_pm = 1 if 17 <= hour <= 20 else 0
        is_night = 1 if (hour >= 22 or hour <= 5) else 0

        # Realistic congestion values — max 1.8 (80% slower)
        if is_peak_am:
            congestion = np.random.uniform(1.3, 1.7)
        elif is_peak_pm:
            congestion = np.random.uniform(1.4, 1.8)
        elif is_night:
            congestion = np.random.uniform(0.95, 1.05)
        else:
            congestion = np.random.uniform(1.05, 1.3)

        # Weekends lighter
        if is_weekend:
            congestion *= np.random.uniform(0.75, 0.90)

        # Monsoon months slightly worse
        if 6 <= month <= 9:
            congestion *= np.random.uniform(1.02, 1.10)

        # Add small noise
        congestion += np.random.normal(0, 0.03)

        # HARD CAP — max 1.8, min 0.95
        congestion = round(max(0.95, min(1.8, congestion)), 4)

        records.append({
            "hour": hour,
            "weekday": weekday,
            "is_weekend": is_weekend,
            "month": month,
            "is_peak_am": is_peak_am,
            "is_peak_pm": is_peak_pm,
            "is_night": is_night,
            "historical_congestion": congestion,
        })
    return pd.DataFrame(records)

def train_svr():
    print("SVR Historical Congestion Model Training")
    df = generate_historical_data(300)
    df.to_csv("svr_training_data.csv", index=False)
    print(f"Generated {len(df)} records")
    X = df[FEATURE_COLS]
    y = df[TARGET_COL]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    pipeline = Pipeline([("scaler", StandardScaler()),("svr", SVR(kernel="rbf", C=10, epsilon=0.05, gamma="scale"))])
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_r2 = cross_val_score(pipeline, X_train, y_train, cv=kf, scoring="r2")
    cv_mae = cross_val_score(pipeline, X_train, y_train, cv=kf, scoring="neg_mean_absolute_error")
    print(f"5-Fold CV Mean R2: {cv_r2.mean():.4f} +/- {cv_r2.std():.4f}")
    print(f"5-Fold CV Mean MAE: {(-cv_mae.mean()):.4f}")
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    print(f"Test R2: {r2_score(y_test, y_pred):.4f}")
    print(f"Test MAE: {mean_absolute_error(y_test, y_pred):.4f}")
    print(f"Test RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")
    return pipeline

def svr_predict(features: dict = None) -> float:
    try:
        model = joblib.load(MODEL_PATH)
        now = features if features else {}
        current_time = datetime.utcnow()
        hour = now.get("hour", current_time.hour)
        weekday = now.get("weekday", current_time.weekday())
        month = now.get("month", current_time.month)
        is_weekend = 1 if weekday >= 5 else 0
        is_peak_am = 1 if 8 <= hour <= 10 else 0
        is_peak_pm = 1 if 17 <= hour <= 20 else 0
        is_night = 1 if (hour >= 22 or hour <= 5) else 0
        row = pd.DataFrame([{"hour":hour,"weekday":weekday,"is_weekend":is_weekend,"month":month,"is_peak_am":is_peak_am,"is_peak_pm":is_peak_pm,"is_night":is_night}])
        prediction = model.predict(row)[0]
        return round(float(prediction), 4)
    except Exception as e:
        logger.error(f"SVR prediction error: {e}")
        return None

if __name__ == "__main__":
    train_svr()
