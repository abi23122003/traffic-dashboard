"""
Real-time traffic monitoring and updates.
"""

import asyncio
from datetime import datetime, UTC, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
import requests
import os
import math

from db import AnalysisResult, SavedRoute
from utils import tomtom_route, summarize_route
from logging_config import get_logger

logger = get_logger(__name__)
TOMTOM_KEY = os.getenv("TOMTOM_KEY")


def _build_bbox(lat: float, lon: float, radius_m: int) -> str:
    """Build TomTom bbox string as minLon,minLat,maxLon,maxLat from center and radius."""
    lat_delta = radius_m / 111320.0
    cos_lat = max(0.1, abs(math.cos(math.radians(lat))))
    lon_delta = radius_m / (111320.0 * cos_lat)

    min_lat = lat - lat_delta
    max_lat = lat + lat_delta
    min_lon = lon - lon_delta
    max_lon = lon + lon_delta
    return f"{min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}"


def _extract_location(geometry: Dict) -> List[float]:
    """Extract a representative [lon, lat] location from incident geometry."""
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        return [coordinates[0], coordinates[1]]

    if geometry_type == "LineString" and isinstance(coordinates, list) and coordinates:
        first = coordinates[0]
        if isinstance(first, list) and len(first) >= 2:
            return [first[0], first[1]]

    return []


def get_traffic_incidents(lat: float, lon: float, radius: int = 5000) -> List[Dict]:
    """Get traffic incidents near a location."""
    if not TOMTOM_KEY:
        return []
    
    try:
        url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
        bbox = _build_bbox(lat, lon, radius)
        params = {
            "key": TOMTOM_KEY,
            "bbox": bbox,
            "fields": "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,startTime,endTime,from,to,length,delay,roadNumbers,timeValidity}}}",
            "language": "en-GB",
            "timeValidityFilter": "present",
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        incidents = []
        for incident in data.get("incidents", []):
            properties = incident.get("properties", {})
            geometry = incident.get("geometry", {})

            description_parts = [
                properties.get("from"),
                properties.get("to"),
            ]
            description = " -> ".join([part for part in description_parts if part])
            if not description:
                description = f"Incident category {properties.get('iconCategory', 'unknown')}"

            incidents.append({
                "id": properties.get("id"),
                "type": incident.get("type"),
                "severity": properties.get("iconCategory") or properties.get("magnitudeOfDelay"),
                "description": description,
                "location": _extract_location(geometry),
                "start_time": properties.get("startTime"),
                "end_time": properties.get("endTime"),
                "delay": properties.get("delay"),
                "length": properties.get("length"),
                "road_numbers": properties.get("roadNumbers"),
                "time_validity": properties.get("timeValidity"),
            })
        
        return incidents
    except Exception as e:
        logger.error(f"Error fetching traffic incidents: {e}")
        return []


async def auto_refresh_route(
    db: Session,
    route_id: str,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    interval_minutes: int = 15
) -> Dict:
    """Auto-refresh route data at intervals."""
    try:
        route_json = tomtom_route(origin_lat, origin_lon, dest_lat, dest_lon, maxAlternatives=1)
        routes = route_json.get("routes", [])
        
        if not routes:
            return {"status": "error", "message": "No routes found"}
        
        route = routes[0]
        summary = summarize_route(route)
        
        # Save to database
        from db import save_analysis
        save_analysis(db, {
            "route_id": route_id,
            "origin": {"lat": origin_lat, "lon": origin_lon},
            "destination": {"lat": dest_lat, "lon": dest_lon},
            "travel_time_s": summary["travel_time_s"],
            "no_traffic_s": summary["no_traffic_s"],
            "delay_s": summary["delay_s"],
            "length_m": summary["length_m"],
            "calculated_cost": 0,  # Will be calculated if needed
        })
        
        return {
            "status": "success",
            "travel_time_min": summary["travel_time_s"] / 60,
            "delay_min": summary["delay_s"] / 60,
            "timestamp": datetime.now(UTC).isoformat()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def monitor_route_changes(
    db: Session,
    route_id: str,
    threshold_percent: float = 20.0
) -> Optional[Dict]:
    """Monitor route for significant changes."""
    # Get last two analyses
    results = db.query(AnalysisResult).filter(
        AnalysisResult.route_id.like(f"{route_id}%")
    ).order_by(AnalysisResult.timestamp.desc()).limit(2).all()
    
    if len(results) < 2:
        return None
    
    latest = results[0]
    previous = results[1]
    
    # Check for significant change
    if latest.travel_time_s and previous.travel_time_s:
        change_percent = abs((latest.travel_time_s - previous.travel_time_s) / previous.travel_time_s) * 100
        
        if change_percent >= threshold_percent:
            return {
                "route_id": route_id,
                "change_percent": round(change_percent, 2),
                "previous_time": previous.travel_time_s / 60,
                "current_time": latest.travel_time_s / 60,
                "timestamp": latest.timestamp.isoformat() if latest.timestamp else None
            }
    
    return None
