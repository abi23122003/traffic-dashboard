"""
Advanced analytics and insights for route analysis.
"""

from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, Float, case, cast
import pandas as pd
import numpy as np
from db import AnalysisResult


def get_peak_hours_analysis(db: Session, route_id: str, days: int = 30) -> Dict:
    """Analyze peak hours for a route."""
    cutoff_date = datetime.now(UTC) - timedelta(days=days)
    
    results = db.query(
        AnalysisResult.hour_of_day,
        func.avg(AnalysisResult.travel_time_s).label('avg_travel_time'),
        func.avg(AnalysisResult.delay_s).label('avg_delay'),
        # Fixed: Use func.nullif to avoid division by zero
        func.avg(
            AnalysisResult.travel_time_s / 
            func.nullif(AnalysisResult.no_traffic_s, 0)
        ).label('avg_congestion'),
        func.count(AnalysisResult.id).label('count')
    ).filter(
        and_(
            AnalysisResult.route_id.like(f"{route_id}%"),
            AnalysisResult.timestamp >= cutoff_date,
            AnalysisResult.no_traffic_s > 0
        )
    ).group_by(AnalysisResult.hour_of_day).all()
    
    if not results:
        return {"peak_hours": [], "off_peak_hours": [], "data": []}
    
    data = []
    for r in results:
        data.append({
            "hour": r.hour_of_day,
            "avg_travel_time": r.avg_travel_time / 60 if r.avg_travel_time else 0,
            "avg_delay": r.avg_delay / 60 if r.avg_delay else 0,
            "avg_congestion": r.avg_congestion if r.avg_congestion else 0,
            "count": r.count
        })
    
    valid_data = [d for d in data if d['avg_travel_time'] > 0 and d['hour'] is not None]
    
    if not valid_data:
        return {"peak_hours": [], "off_peak_hours": [], "data": data}
    
    sorted_data = sorted(valid_data, key=lambda x: x['avg_travel_time'], reverse=True)
    peak_hours = [d['hour'] for d in sorted_data[:3]]
    off_peak_hours = [d['hour'] for d in sorted_data[-3:]]
    
    return {
        "peak_hours": peak_hours,
        "off_peak_hours": off_peak_hours,
        "data": data,
        "best_hour": sorted_data[-1]['hour'] if sorted_data else None,
        "worst_hour": sorted_data[0]['hour'] if sorted_data else None
    }


def get_day_of_week_analysis(db: Session, route_id: str, days: int = 90) -> Dict:
    """Analyze day of week patterns."""
    cutoff_date = datetime.now(UTC) - timedelta(days=days)
    
    results = db.query(
        AnalysisResult.day_of_week,
        func.avg(AnalysisResult.travel_time_s).label('avg_travel_time'),
        func.avg(AnalysisResult.delay_s).label('avg_delay'),
        func.avg(AnalysisResult.calculated_cost).label('avg_cost'),
        func.count(AnalysisResult.id).label('count')
    ).filter(
        and_(
            AnalysisResult.route_id.like(f"{route_id}%"),
            AnalysisResult.timestamp >= cutoff_date
        )
    ).group_by(AnalysisResult.day_of_week).all()
    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    data = []
    for r in results:
        if r.day_of_week is not None:
            data.append({
                "day": day_names[r.day_of_week] if 0 <= r.day_of_week < 7 else 'Unknown',
                "day_index": r.day_of_week,
                "avg_travel_time": r.avg_travel_time / 60 if r.avg_travel_time else 0,
                "avg_delay": r.avg_delay / 60 if r.avg_delay else 0,
                "avg_cost": r.avg_cost if r.avg_cost else 0,
                "count": r.count
            })
    
    weekday_data = [d for d in data if d['day_index'] is not None and d['day_index'] < 5]
    weekend_data = [d for d in data if d['day_index'] is not None and d['day_index'] >= 5]
    
    weekday_avg = sum([d['avg_travel_time'] for d in weekday_data]) / max(len(weekday_data), 1)
    weekend_avg = sum([d['avg_travel_time'] for d in weekend_data]) / max(len(weekend_data), 1)
    
    valid_data = [d for d in data if d['avg_travel_time'] > 0]
    best_day = min(valid_data, key=lambda x: x['avg_travel_time'])['day'] if valid_data else None
    worst_day = max(valid_data, key=lambda x: x['avg_travel_time'])['day'] if valid_data else None
    
    return {
        "data": data,
        "weekday_avg": weekday_avg,
        "weekend_avg": weekend_avg,
        "best_day": best_day,
        "worst_day": worst_day
    }


def get_seasonal_trends(db: Session, route_id: str, months: int = 12) -> Dict:
    """Analyze seasonal/monthly trends."""
    cutoff_date = datetime.now(UTC) - timedelta(days=months * 30)
    
    results = db.query(
        AnalysisResult.month,
        func.avg(AnalysisResult.travel_time_s).label('avg_travel_time'),
        func.avg(AnalysisResult.delay_s).label('avg_delay'),
        func.count(AnalysisResult.id).label('count')
    ).filter(
        and_(
            AnalysisResult.route_id.like(f"{route_id}%"),
            AnalysisResult.timestamp >= cutoff_date,
            AnalysisResult.month.isnot(None)
        )
    ).group_by(AnalysisResult.month).all()
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    data = []
    for r in results:
        if r.month and 1 <= r.month <= 12:
            data.append({
                "month": month_names[r.month - 1],
                "month_index": r.month,
                "avg_travel_time": r.avg_travel_time / 60 if r.avg_travel_time else 0,
                "avg_delay": r.avg_delay / 60 if r.avg_delay else 0,
                "count": r.count
            })
    
    return {"data": data}


def calculate_route_reliability(db: Session, route_id: str, days: int = 30) -> Dict:
    """Calculate route reliability score (0-100)."""
    cutoff_date = datetime.now(UTC) - timedelta(days=days)
    
    results = db.query(AnalysisResult).filter(
        and_(
            AnalysisResult.route_id.like(f"{route_id}%"),
            AnalysisResult.timestamp >= cutoff_date,
            AnalysisResult.travel_time_s.isnot(None),
            AnalysisResult.travel_time_s > 0
        )
    ).all()
    
    if not results or len(results) < 5:
        return {"reliability_score": None, "consistency": None, "data_points": len(results)}
    
    travel_times = [r.travel_time_s / 60 for r in results if r.travel_time_s]
    
    if not travel_times:
        return {"reliability_score": None, "consistency": None, "data_points": 0}
    
    avg_time = np.mean(travel_times)
    std_time = np.std(travel_times)
    
    cv = (std_time / avg_time) if avg_time > 0 else 1.0
    reliability_score = max(0, min(100, (1 - cv) * 100))
    
    within_range = sum(1 for t in travel_times if abs(t - avg_time) / avg_time <= 0.2)
    consistency = (within_range / len(travel_times)) * 100
    
    return {
        "reliability_score": round(reliability_score, 2),
        "consistency": round(consistency, 2),
        "avg_travel_time": round(avg_time, 2),
        "std_travel_time": round(std_time, 2),
        "min_time": round(min(travel_times), 2),
        "max_time": round(max(travel_times), 2),
        "data_points": len(results)
    }


def predict_future_congestion(db: Session, route_id: str, hours_ahead: int = 24) -> Dict:
    """Predict future congestion using historical patterns."""
    current_hour = datetime.now(UTC).hour
    target_hour = (current_hour + hours_ahead) % 24
    
    results = db.query(AnalysisResult).filter(
        and_(
            AnalysisResult.route_id.like(f"{route_id}%"),
            AnalysisResult.hour_of_day == target_hour,
            AnalysisResult.no_traffic_s > 0,
            AnalysisResult.travel_time_s > 0
        )
    ).order_by(AnalysisResult.timestamp.desc()).limit(50).all()
    
    if not results:
        return {"predicted_congestion": None, "confidence": None}
    
    congestion_ratios = []
    for r in results:
        if r.no_traffic_s and r.no_traffic_s > 0:
            ratio = r.travel_time_s / r.no_traffic_s
            if ratio > 0:
                congestion_ratios.append(ratio)
    
    if not congestion_ratios:
        return {"predicted_congestion": None, "confidence": None}
    
    predicted = np.mean(congestion_ratios)
    std = np.std(congestion_ratios)
    confidence = max(0, min(100, (1 - (std / predicted)) * 100)) if predicted > 0 else 0
    
    predicted_travel_time = None
    if results[0].no_traffic_s:
        predicted_travel_time = round(predicted * (results[0].no_traffic_s / 60), 2)
    
    return {
        "predicted_congestion": round(predicted, 2),
        "confidence": round(confidence, 2),
        "predicted_travel_time": predicted_travel_time,
        "data_points": len(congestion_ratios)
    }


def get_traffic_hotspots(db: Session, days: int = 7) -> List[Dict]:
    """Identify traffic hotspots (routes with highest congestion)."""
    cutoff_date = datetime.now(UTC) - timedelta(days=days)
    
    results = db.query(
        AnalysisResult.route_id,
        func.avg(AnalysisResult.delay_s).label('avg_delay'),
        func.avg(
            AnalysisResult.travel_time_s / func.nullif(AnalysisResult.no_traffic_s, 0)
        ).label('avg_congestion'),
        func.count(AnalysisResult.id).label('count')
    ).filter(
        and_(
            AnalysisResult.timestamp >= cutoff_date,
            AnalysisResult.no_traffic_s > 0,
            AnalysisResult.travel_time_s > 0
        )
    ).group_by(AnalysisResult.route_id).having(
        func.count(AnalysisResult.id) >= 5
    ).order_by(
        func.avg(AnalysisResult.delay_s).desc()
    ).limit(10).all()
    
    hotspots = []
    for r in results:
        if r.avg_delay:
            hotspots.append({
                "route_id": r.route_id,
                "avg_delay_minutes": round(r.avg_delay / 60, 2),
                "avg_congestion": round(r.avg_congestion, 2) if r.avg_congestion else None,
                "analysis_count": r.count
            })
    
    return hotspots