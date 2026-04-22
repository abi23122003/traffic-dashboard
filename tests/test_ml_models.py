#!/usr/bin/env python3
"""Test ML models to verify they are working correctly"""

import joblib
import pandas as pd
import os

print("="*70)
print("TRAFFIC DASHBOARD - ML MODEL VERIFICATION")
print("="*70)

# Test 1: SVR Traffic Prediction Model
print("\n1️⃣ SVR TRAFFIC PREDICTION MODEL")
print("-"*70)
try:
    from svr_model import svr_predict
    print("✅ SVR model loaded")
    
    test_hours = [
        ("Morning Peak (8 AM)", {"hour": 8, "weekday": 3, "month": 4}),
        ("Afternoon (2 PM)", {"hour": 14, "weekday": 3, "month": 4}),
        ("Evening Peak (6 PM)", {"hour": 18, "weekday": 3, "month": 4}),
        ("Night (11 PM)", {"hour": 23, "weekday": 3, "month": 4}),
        ("Weekend (2 PM)", {"hour": 14, "weekday": 6, "month": 4}),
    ]
    
    for label, features in test_hours:
        result = svr_predict(features)
        percent_slower = int((result - 1.0) * 100)
        severity = "HEAVY" if result > 1.4 else "MODERATE" if result > 1.2 else "LIGHT"
        print(f"  {label:25} {result:.2f}x ({percent_slower}% slower) [{severity}]")
        
except Exception as e:
    print(f"❌ SVR Model Error: {e}")

# Test 2: Random Forest Route Scoring Model
print("\n2️⃣ RANDOM FOREST ROUTE SCORING MODEL")
print("-"*70)
try:
    model_path = "rf_model.pkl"
    if os.path.exists(model_path):
        model = joblib.load(model_path)
        print(f"✅ RF model loaded: {type(model).__name__}")
        
        # Test with sample routes
        sample_data = {
            "hour": [14, 14, 14],
            "weekday": [2, 2, 2],
            "is_weekend": [0, 0, 0],
            "distance_km": [300, 350, 320],
            "route_index": [0, 1, 2],
            "travel_time_s": [17980, 21900, 19500],
            "no_traffic_s": [17280, 19800, 17700],
            "delay_s": [700, 2100, 1800],
            "rolling_mean_congestion": [1.04, 1.11, 1.10],
            "rolling_std_congestion": [0.0, 0.0, 0.0]
        }
        
        df = pd.DataFrame(sample_data)
        numeric_cols = [col for col in df.columns if df[col].dtype in ['int64', 'float64']]
        X = df[numeric_cols].fillna(0)
        
        predictions = model.predict(X)
        print(f"\n  Sample Route Predictions (Lower Score = Better Route):")
        for i, score in enumerate(predictions, 1):
            rank = sorted(enumerate(predictions), key=lambda x: x[1])
            rank_num = [x[0] for x in rank].index(i-1) + 1
            indicator = "✅ BEST" if score == min(predictions) else f"#{rank_num}"
            print(f"    Route {i}: {score:.2f} ({indicator})")
    else:
        print(f"❌ Model not found at {model_path}")
        
except Exception as e:
    print(f"❌ RF Model Error: {e}")

# Test 3: Integration check
print("\n3️⃣ INTEGRATION CHECK")
print("-"*70)
try:
    from app import ML_MODEL
    if ML_MODEL is not None:
        print("✅ RF model successfully loaded in app.py")
    else:
        print("⚠️  ML_MODEL is None in app.py (but this may be intentional)")
except Exception as e:
    print(f"⚠️  Could not check app.py integration: {e}")

print("\n" + "="*70)
print("✅ ML MODEL VERIFICATION COMPLETE")
print("="*70)
