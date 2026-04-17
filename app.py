"""
FastAPI backend for traffic route analysis.
Provides endpoints for autocomplete, route analysis, and serving the frontend.
"""

import os
import json
from typing import Optional, Union, List
from functools import wraps
from fastapi import FastAPI, HTTPException, Query, Depends, status, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse, Response, RedirectResponse
import io
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, EmailStr, field_validator
import joblib
from datetime import datetime, UTC, timedelta
import secrets
import uuid
import traceback

# Import logging and rate limiting
from logging_config import setup_logging, get_logger
from rate_limiter import RateLimitMiddleware

# Setup logging
setup_logging()
logger = get_logger(__name__)

from utils import (
    tomtom_geocode,
    tomtom_autocomplete,
    tomtom_route,
    summarize_route,
    compute_route_cost,
    haversine_m
)
from db import (
    init_db, get_session, save_analysis, AnalysisResult,
    User, SavedRoute, RouteRating, Notification
)
from sqlalchemy.orm import Session
from auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, get_current_active_user, get_current_admin_user,
    authenticate_user, create_user, get_user_by_username, Token, UserCreate as AuthUserCreate, UserResponse,
    get_optional_user, RoleLoginRequest, RoleToken, UserRole, create_role_access_token, require_role
)
from analytics import (
    get_peak_hours_analysis, get_day_of_week_analysis,
    get_seasonal_trends, calculate_route_reliability, predict_future_congestion,
    get_traffic_hotspots
)
from export_utils import export_to_csv, export_to_excel, export_to_pdf
from notifications import (
    create_notification, check_traffic_alerts,
    suggest_best_time_to_leave, check_congestion_warnings,
    get_user_notifications, mark_notification_read
)
from cache_utils import cached, clear_cache, get_cache_stats
from realtime_utils import get_traffic_incidents, auto_refresh_route, monitor_route_changes

# Initialize FastAPI app
app = FastAPI(
    title="Traffic Route Analysis API",
    description="Real-time traffic congestion analysis with ML predictions",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

templates = Jinja2Templates(directory="templates")

# Initialize database
init_db()

# Load ML model if available
ML_MODEL = None
MODEL_PATH = os.getenv("MODEL_PATH", "rf_model.pkl")
if os.path.exists(MODEL_PATH):
    try:
        ML_MODEL = joblib.load(MODEL_PATH)
        logger.info(f"✅ Loaded ML model from {MODEL_PATH}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to load ML model: {e}")

# Mount static files if directory exists
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================================
# ERROR HANDLING DECORATOR
# ============================================================================

def handle_db_errors(func):
    """Decorator to handle database errors gracefully."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database operation failed: {str(e)}"
            )
    return wrapper


DISTRICT_LOCATIONS = {
    "district_1": {"lat": 13.0827, "lon": 80.2707, "name": "Central District"},
    "district_2": {"lat": 13.0545, "lon": 80.2450, "name": "West District"},
    "district_3": {"lat": 12.9716, "lon": 80.1534, "name": "South District"},
    "district_4": {"lat": 13.1278, "lon": 80.2270, "name": "North District"},
}


def _normalize_severity(raw_severity: Optional[str]) -> str:
    value = (raw_severity or "").lower()
    if value in {"1", "low", "minor"}:
        return "low"
    if value in {"2", "moderate", "medium"}:
        return "moderate"
    if value in {"3", "high"}:
        return "high"
    return "unknown"


def _severity_color(severity: Optional[str]) -> str:
    palette = {
        "low": "#22c55e",
        "moderate": "#f59e0b",
        "high": "#ef4444",
        "unknown": "#64748b",
    }
    return palette.get(_normalize_severity(severity), "#64748b")


def _load_police_incidents(district_id: str) -> list[dict]:
    district = DISTRICT_LOCATIONS.get(district_id, DISTRICT_LOCATIONS["district_1"])
    incidents = get_traffic_incidents(district["lat"], district["lon"], radius=7000)

    normalized: list[dict] = []
    for index, incident in enumerate(incidents):
        location = incident.get("location") or []
        latitude = None
        longitude = None
        if isinstance(location, (list, tuple)) and len(location) >= 2:
            longitude, latitude = location[0], location[1]
        normalized.append({
            "id": incident.get("id") or f"incident-{index}",
            "type": incident.get("type") or "traffic",
            "severity": _normalize_severity(incident.get("severity")),
            "severity_color": _severity_color(incident.get("severity")),
            "description": incident.get("description") or "Traffic incident",
            "latitude": latitude,
            "longitude": longitude,
            "start_time": incident.get("start_time"),
            "end_time": incident.get("end_time"),
            "district_id": district_id,
            "response_time": incident.get("response_time") or incident.get("responseTime"),
        })

    return normalized


def _build_district_summary(incidents: list[dict]) -> dict:
    today = datetime.now(UTC).date()
    today_count = 0
    response_times: list[float] = []

    for incident in incidents:
        start_time = incident.get("start_time")
        if start_time:
            try:
                parsed = datetime.fromisoformat(str(start_time).replace("Z", "+00:00"))
                if parsed.date() == today:
                    today_count += 1
            except ValueError:
                today_count += 1
        else:
            today_count += 1

        response_time = incident.get("response_time")
        if isinstance(response_time, (int, float)):
            response_times.append(float(response_time))

    avg_response_time = round(sum(response_times) / len(response_times), 2) if response_times else 0.0
    return {
        "total_incidents_today": today_count,
        "avg_response_time": avg_response_time,
    }


def _district_prediction_candidates(district_id: str, incidents: list[dict]) -> list[dict]:
    district = DISTRICT_LOCATIONS.get(district_id, DISTRICT_LOCATIONS["district_1"])
    candidates: list[dict] = []

    for incident in incidents:
        if incident.get("latitude") is not None and incident.get("longitude") is not None:
            candidates.append({
                "location": incident.get("description") or "Incident hotspot",
                "latitude": incident["latitude"],
                "longitude": incident["longitude"],
                "base_severity": incident.get("severity", "unknown"),
                "source": "live_incident",
            })

    if not candidates:
        offsets = [
            (0.0000, 0.0000),
            (0.0120, 0.0080),
            (-0.0100, 0.0110),
            (0.0090, -0.0090),
            (-0.0080, -0.0100),
        ]
        for index, (lat_offset, lon_offset) in enumerate(offsets):
            candidates.append({
                "location": f"{district['name']} sector {index + 1}",
                "latitude": district["lat"] + lat_offset,
                "longitude": district["lon"] + lon_offset,
                "base_severity": "unknown",
                "source": "district_grid",
            })

    return candidates[:10]


def _predict_police_hotspots(district_id: str, incidents: list[dict]) -> list[dict]:
    """Use the existing loaded ML model to rank likely hotspot locations."""
    candidates = _district_prediction_candidates(district_id, incidents)
    if not candidates:
        return []

    now = datetime.now(UTC)
    predictions: list[dict] = []

    for candidate in candidates:
        hourly_scores: list[float] = []
        for hours_ahead in range(1, 7):
            future_time = now + timedelta(hours=hours_ahead)
            distance_km = haversine_m(
                candidate["latitude"],
                candidate["longitude"],
                DISTRICT_LOCATIONS.get(district_id, DISTRICT_LOCATIONS["district_1"])["lat"],
                DISTRICT_LOCATIONS.get(district_id, DISTRICT_LOCATIONS["district_1"])["lon"],
            ) / 1000.0

            severity_bias = {
                "low": 0.05,
                "moderate": 0.15,
                "high": 0.30,
                "unknown": 0.10,
            }.get(candidate.get("base_severity", "unknown"), 0.10)

            feature_frame = {
                "hour": future_time.hour,
                "weekday": future_time.weekday(),
                "is_weekend": 1 if future_time.weekday() >= 5 else 0,
                "distance_km": max(distance_km, 0.1),
                "route_index": 0,
                "travel_time_s": 900 + int(distance_km * 180) + int(severity_bias * 300),
                "no_traffic_s": 750 + int(distance_km * 120),
                "delay_s": 150 + int(severity_bias * 240),
                "rolling_mean_congestion": 1.0 + severity_bias,
                "rolling_std_congestion": 0.05 + severity_bias / 2,
            }

            model_prediction = predict_congestion(feature_frame)
            if model_prediction is None:
                model_prediction = 1.0 + severity_bias

            likelihood_score = max(0.0, min(100.0, ((float(model_prediction) - 0.9) / 1.2) * 100 + severity_bias * 15))
            hourly_scores.append(likelihood_score)

        average_score = round(sum(hourly_scores) / len(hourly_scores), 2)
        confidence = round(max(0.0, min(100.0, 100.0 - (max(hourly_scores) - min(hourly_scores)) * 0.75)), 2)

        if average_score >= 85:
            predicted_type = "critical congestion"
        elif average_score >= 70:
            predicted_type = "high traffic"
        elif average_score >= 50:
            predicted_type = "moderate traffic"
        else:
            predicted_type = "light traffic"

        predictions.append({
            "location": candidate["location"],
            "likelihood_score": average_score,
            "confidence": confidence,
            "predicted_type": predicted_type,
        })

    predictions.sort(key=lambda item: item["likelihood_score"], reverse=True)
    return predictions[:5]


def _safe_ppt_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _format_ppt_timestamp(value: Optional[str]) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)

# ============================================================================
# VALIDATION MODELS (Pydantic V2 Compatible)
# ============================================================================

class ValidatedCoordinates(BaseModel):
    """Validated coordinate pair."""
    lat: float
    lon: float
    
    @field_validator('lat')
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Validate latitude is within -90 to 90."""
        if v is None:
            raise ValueError('Latitude is required')
        if not -90 <= v <= 90:
            raise ValueError(f'Invalid latitude: {v}. Must be between -90 and 90')
        return v
    
    @field_validator('lon')
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Validate longitude is within -180 to 180."""
        if v is None:
            raise ValueError('Longitude is required')
        if not -180 <= v <= 180:
            raise ValueError(f'Invalid longitude: {v}. Must be between -180 and 180')
        return v


class RouteAnalysisRequest(BaseModel):
    """Request model for route analysis with validation."""
    origin: Union[str, dict] = Field(..., description="Origin as place name or {lat, lon}")
    destination: Union[str, dict] = Field(..., description="Destination as place name or {lat, lon}")
    maxAlternatives: int = Field(3, ge=1, le=5, description="Maximum route alternatives")
    alpha: float = Field(1.0, ge=0, le=10, description="Weight for travel time in cost calculation")
    beta: float = Field(0.5, ge=0, le=10, description="Weight for delay in cost calculation")
    gamma: float = Field(0.001, ge=0, le=1, description="Weight for distance in cost calculation")
    avoid_tolls: bool = Field(False, description="Avoid toll roads")
    avoid_ferries: bool = Field(False, description="Avoid ferries")
    avoid_highways: bool = Field(False, description="Avoid highways")
    
    @field_validator('maxAlternatives')
    @classmethod
    def validate_max_alternatives(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError('maxAlternatives must be between 1 and 5')
        return v
    
    @field_validator('alpha', 'beta', 'gamma')
    @classmethod
    def validate_weights(cls, v: float, info) -> float:
        if v < 0:
            raise ValueError(f'{info.field_name} cannot be negative')
        return v


class UserCreate(BaseModel):
    """User registration model."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login model."""
    username: str
    password: str


class SavedRouteCreate(BaseModel):
    """Create saved route model."""
    route_name: str
    origin: Union[str, dict]
    destination: Union[str, dict]
    route_preferences: Optional[dict] = None


class RouteRatingCreate(BaseModel):
    """Create route rating model."""
    route_id: str
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None


class ShareRouteRequest(BaseModel):
    """Share route request model."""
    route_id: str
    route_index: Optional[int] = None


class UserUpdate(BaseModel):
    """User update model for admin editing."""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """
    Decode Google-style polyline string to list of (lat, lon) tuples.
    Handles TomTom's coordinate formats properly.
    
    Args:
        encoded: Encoded polyline string or coordinate list
        
    Returns:
        List of (latitude, longitude) tuples
    """
    if not encoded:
        return []
    
    # Handle if encoded is already a list of coordinates
    if isinstance(encoded, list):
        coordinates = []
        for p in encoded:
            try:
                if isinstance(p, dict):
                    if "lat" in p and "lon" in p:
                        coordinates.append((float(p["lat"]), float(p["lon"])))
                    elif "latitude" in p and "longitude" in p:
                        coordinates.append((float(p["latitude"]), float(p["longitude"])))
                elif isinstance(p, (list, tuple)) and len(p) >= 2:
                    coordinates.append((float(p[0]), float(p[1])))
            except (ValueError, TypeError):
                continue
        return coordinates
    
    # Try to use the polyline library if available
    try:
        import polyline
        return polyline.decode(encoded)
    except ImportError:
        # Fallback to custom decoder if polyline not installed
        pass
    except Exception as e:
        logger.warning(f"Polyline library decoding failed: {e}")
    
    # Custom decoder implementation
    coordinates = []
    index = 0
    lat = 0
    lon = 0
    
    try:
        while index < len(encoded):
            # Decode latitude
            shift = 0
            result = 0
            while index < len(encoded):
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = ~(result >> 1) if (result & 1) else (result >> 1)
            lat += dlat
            
            # Check if we have enough characters for longitude
            if index >= len(encoded):
                break
                
            # Decode longitude
            shift = 0
            result = 0
            while index < len(encoded):
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlon = ~(result >> 1) if (result & 1) else (result >> 1)
            lon += dlon
            
            coordinates.append((lat / 1e5, lon / 1e5))
    except (IndexError, ValueError, TypeError) as e:
        logger.error(f"Polyline decoding error: {e}")
        return []
    
    return coordinates


def extract_route_geometry(route_json: dict) -> list[tuple[float, float]]:
    """
    Extract route geometry from TomTom route JSON.
    
    Args:
        route_json: Route object from TomTom API
        
    Returns:
        List of (lat, lon) tuples for route path
    """
    geometry = []
    
    try:
        legs = route_json.get("legs", [])
        for leg in legs:
            points = leg.get("points", [])
            for point in points:
                if isinstance(point, dict):
                    if "latitude" in point and "longitude" in point:
                        try:
                            geometry.append((float(point["latitude"]), float(point["longitude"])))
                        except (ValueError, TypeError):
                            continue
                    elif "lat" in point and "lon" in point:
                        try:
                            geometry.append((float(point["lat"]), float(point["lon"])))
                        except (ValueError, TypeError):
                            continue
        
        if not geometry:
            guidance = route_json.get("guidance", {})
            instructions = guidance.get("instructions", [])
            for instruction in instructions:
                point = instruction.get("point", {})
                if "latitude" in point and "longitude" in point:
                    try:
                        geometry.append((float(point["latitude"]), float(point["longitude"])))
                    except (ValueError, TypeError):
                        continue
    except Exception as e:
        logger.error(f"Error extracting route geometry: {e}")
        return []
    
    return geometry


def predict_congestion(features: dict) -> Optional[float]:
    """
    Predict route score using RF model.
    Lower score = better route.
    """
    if ML_MODEL is None:
        return None
    try:
        import pandas as pd
        now = datetime.now(UTC)
        feature_dict = {
            "hour": now.hour,
            "weekday": now.weekday(),
            "is_weekend": 1 if now.weekday() >= 5 else 0,
            "distance_km": features.get("distance_km", 0),
            "route_index": features.get("route_index", 0),
            "travel_time_s": features.get("travel_time_s", 0),
            "no_traffic_s": features.get("no_traffic_s", 0),
            "delay_s": features.get("delay_s", 0),
            "rolling_mean_congestion": features.get("rolling_mean_congestion", 1.0),
            "rolling_std_congestion": features.get("rolling_std_congestion", 0.0)
        }
        df = pd.DataFrame([feature_dict])
        numeric_cols = [col for col in df.columns if df[col].dtype in ['int64', 'float64']]
        X = df[numeric_cols].fillna(0)
        prediction = ML_MODEL.predict(X)[0]
        return round(float(prediction), 2)
    except Exception as e:
        logger.error(f"ML prediction error: {e}")
        return None


# ============================================================================
# FRONTEND ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main frontend HTML page. Authentication is checked client-side."""
    index_path = os.path.join("templates", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>Traffic Route Analysis API</h1><p>Frontend not found. Please create templates/index.html</p>",
        status_code=404
    )


@app.get("/favicon.ico")
async def serve_favicon():
    """Serve the favicon."""
    favicon_path = os.path.join("static", "favicon.svg")
    if os.path.exists(favicon_path):
        with open(favicon_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="image/svg+xml")
    # Return a default empty response to prevent 404 logs
    return Response(content="", status_code=204)


@app.get("/login", response_class=HTMLResponse)
async def serve_login():
    """Serve the login/registration page."""
    login_path = os.path.join("templates", "login.html")
    if os.path.exists(login_path):
        with open(login_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>Login</h1><p>Login page not found.</p>",
        status_code=404
    )


@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    """Serve the admin dashboard page."""
    admin_path = os.path.join("templates", "admin.html")
    if os.path.exists(admin_path):
        with open(admin_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>Admin Dashboard</h1><p>Admin page not found.</p>",
        status_code=404
    )


@app.get("/account", response_class=HTMLResponse)
async def serve_account():
    """Serve the user account page."""
    account_path = os.path.join("templates", "account.html")
    if os.path.exists(account_path):
        with open(account_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>My Account</h1><p>Account page not found.</p>",
        status_code=404
    )


@app.get("/password-toggle-demo", response_class=HTMLResponse)
async def serve_password_toggle_demo():
    """Serve the password toggle demo page."""
    demo_path = os.path.join("templates", "password_toggle_demo.html")
    if os.path.exists(demo_path):
        with open(demo_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>Password Toggle Demo</h1><p>Demo page not found.</p>",
        status_code=404
    )


@app.get("/analysis-report", response_class=HTMLResponse)
async def serve_analysis_report():
    """Serve the analysis report HTML page."""
    report_path = os.path.join("templates", "analysis_report.html")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>Analysis Report</h1><p>Report page not found.</p>",
        status_code=404
    )


@app.get("/static/manifest.json")
async def get_manifest():
    """Serve PWA manifest."""
    manifest_path = os.path.join("static", "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/json")
    return JSONResponse({"error": "Manifest not found"}, status_code=404)


# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": ML_MODEL is not None,
        "timestamp": datetime.now(UTC).isoformat()
    }


@app.get("/api/stats")
async def get_stats():
    """Get real statistics from database for stats bar."""
    try:
        session = get_session()
        
        # Count routes analyzed today
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = session.query(AnalysisResult).filter(
            AnalysisResult.timestamp >= today_start
        ).count()
        
        # Get average congestion from last 10 records
        recent_records = session.query(AnalysisResult).order_by(
            AnalysisResult.timestamp.desc()
        ).limit(10).all()
        
        avg_congestion = 1.0
        if recent_records:
            ratios = []
            for r in recent_records:
                if r.travel_time_s and r.no_traffic_s and r.no_traffic_s > 0:
                    ratios.append(r.travel_time_s / r.no_traffic_s)
            if ratios:
                avg_congestion = round(sum(ratios) / len(ratios), 2)
        
        # Traffic status based on congestion
        if avg_congestion < 1.15:
            traffic_status = "Light"
            status_color = "#42a5f5"
        elif avg_congestion < 1.5:
            traffic_status = "Moderate"
            status_color = "#ffa726"
        else:
            traffic_status = "Heavy"
            status_color = "#ef5350"
        
        # Total all time count
        total_count = session.query(AnalysisResult).count()
        session.close()
        
        return {
            "routes_today": today_count,
            "total_routes": total_count,
            "avg_congestion": avg_congestion,
            "traffic_status": traffic_status,
            "status_color": status_color
        }
    except Exception as e:
        return {
            "routes_today": 0,
            "total_routes": 0,
            "avg_congestion": 1.0,
            "traffic_status": "Light",
            "status_color": "#42a5f5"
        }


@app.get("/autocomplete")
async def autocomplete(q: str = Query(..., description="Search query")):
    """
    Get autocomplete suggestions from TomTom API.
    
    Args:
        q: Search query string
        
    Returns:
        List of suggestion objects
    """
    try:
        suggestions = tomtom_autocomplete(q)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Autocomplete failed: {str(e)}")


@app.post("/analyze-route")
async def analyze_route(
    request: RouteAnalysisRequest,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Analyze route alternatives with cost calculation and ML prediction.
    
    Args:
        request: RouteAnalysisRequest with origin, destination, and parameters
        current_user: Optional authenticated user
        
    Returns:
        JSON with analyzed routes and best route recommendation
    """
    try:
        # Parse and validate origin
        if isinstance(request.origin, str):
            o_lat, o_lon = tomtom_geocode(request.origin)
            origin_data = {"name": request.origin, "lat": o_lat, "lon": o_lon}
        else:
            o_lat = float(request.origin.get("lat"))
            o_lon = float(request.origin.get("lon"))
            origin_data = request.origin
        
        # Parse and validate destination
        if isinstance(request.destination, str):
            d_lat, d_lon = tomtom_geocode(request.destination)
            dest_data = {"name": request.destination, "lat": d_lat, "lon": d_lon}
        else:
            d_lat = float(request.destination.get("lat"))
            d_lon = float(request.destination.get("lon"))
            dest_data = request.destination
        
        # Validate coordinates
        if not (-90 <= o_lat <= 90) or not (-180 <= o_lon <= 180):
            raise ValueError("Invalid origin coordinates")
        if not (-90 <= d_lat <= 90) or not (-180 <= d_lon <= 180):
            raise ValueError("Invalid destination coordinates")
        
        # Fetch routes from TomTom
        route_json = tomtom_route(
            o_lat, o_lon, d_lat, d_lon,
            maxAlternatives=request.maxAlternatives
        )
        
        routes = route_json.get("routes", [])
        if not routes:
            raise HTTPException(status_code=404, detail="No routes found")
        
        # Analyze each route
        analyzed_routes = []
        route_id = f"{origin_data.get('name', f'{o_lat},{o_lon}')}→{dest_data.get('name', f'{d_lat},{d_lon}')}"
        
        for idx, route in enumerate(routes):
            summary = summarize_route(route)
            
            if summary["length_m"] == 0:
                summary["length_m"] = haversine_m(o_lat, o_lon, d_lat, d_lon)
            
            cost = compute_route_cost(
                summary["travel_time_s"],
                summary["no_traffic_s"],
                summary["delay_s"],
                summary["length_m"],
                alpha=request.alpha,
                beta=request.beta,
                gamma=request.gamma
            )
            
            ml_predicted = predict_congestion({
                "distance_km": summary["length_m"] / 1000.0,
                "route_index": idx,
                "travel_time_s": summary["travel_time_s"],
                "no_traffic_s": summary["no_traffic_s"],
                "delay_s": summary["delay_s"]
            })
            
            svr_predicted = None
            try:
                from svr_model import svr_predict
                svr_predicted = svr_predict({})
            except Exception as e:
                svr_predicted = None
            
            congestion_ratio = (
                summary["travel_time_s"] / summary["no_traffic_s"]
                if summary["no_traffic_s"] and summary["no_traffic_s"] > 0
                else None
            )
            
            geometry = extract_route_geometry(route)
            
            calculated_delay = 0
            if summary["travel_time_s"] and summary["no_traffic_s"]:
                calculated_delay = max(0, summary["travel_time_s"] - summary["no_traffic_s"])
            elif summary.get("delay_s"):
                calculated_delay = summary["delay_s"]
            
            analyzed_route = {
                "route_index": idx,
                "travel_time_s": summary["travel_time_s"],
                "no_traffic_s": summary["no_traffic_s"],
                "delay_s": calculated_delay,
                "length_m": summary["length_m"],
                "congestion_ratio": congestion_ratio,
                "calculated_cost": cost,
                "ml_predicted_congestion": ml_predicted,
                "svr_predicted_congestion": svr_predicted,
                "geometry": geometry
            }
            analyzed_routes.append(analyzed_route)
            
            # Save to database
            try:
                session = get_session()
                save_analysis(session, {
                    "route_id": f"{route_id}_route{idx}",
                    "origin": origin_data,
                    "destination": dest_data,
                    "travel_time_s": summary["travel_time_s"],
                    "no_traffic_s": summary["no_traffic_s"],
                    "delay_s": summary["delay_s"],
                    "length_m": summary["length_m"],
                    "calculated_cost": cost,
                    "ml_predicted": ml_predicted,
                    "raw_json": route,
                    "user_id": current_user.id if current_user else None
                })
                session.close()
            except Exception as e:
                logger.error(f"Database save error: {e}")
        
        # Find best route (lowest cost)
        best_route = min(analyzed_routes, key=lambda x: x["calculated_cost"])
        
        return {
            "origin": origin_data,
            "destination": dest_data,
            "analyzed_routes": analyzed_routes,
            "best_route_index": best_route["route_index"],
            "best_route": best_route,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Route analysis error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Route analysis failed: {str(e)}")


@app.get("/api/route-analysis/{route_id}")
async def get_route_analysis(route_id: str, route_index: Optional[int] = None):
    """
    Get detailed analysis data for a specific route.
    
    Args:
        route_id: Route identifier (e.g., "Origin→Destination")
        route_index: Optional route index to filter specific route variant
        
    Returns:
        Analysis data with historical trends and statistics
    """
    try:
        session = get_session()
        
        route_id = route_id.replace('%E2%86%92', '→')
        
        if route_index is not None:
            query = session.query(AnalysisResult).filter(
                AnalysisResult.route_id == f"{route_id}_route{route_index}"
            )
        else:
            query = session.query(AnalysisResult).filter(
                AnalysisResult.route_id.like(f"{route_id}_route%")
            )
        
        results = query.order_by(AnalysisResult.timestamp.desc()).all()
        session.close()
        
        if not results:
            raise HTTPException(status_code=404, detail="No analysis data found for this route")
        
        analysis_data = []
        for r in results:
            try:
                origin = json.loads(r.origin) if r.origin and r.origin.startswith('{') else {"name": r.origin}
                dest = json.loads(r.destination) if r.destination and r.destination.startswith('{') else {"name": r.destination}
            except:
                origin = {"name": r.origin}
                dest = {"name": r.destination}
            
            delay_val = r.delay_s
            if delay_val is None or delay_val == 0:
                if r.travel_time_s and r.no_traffic_s:
                    delay_val = max(0, r.travel_time_s - r.no_traffic_s)
                else:
                    delay_val = 0
            
            analysis_data.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "route_id": r.route_id,
                "origin": origin,
                "destination": dest,
                "travel_time_s": r.travel_time_s,
                "no_traffic_s": r.no_traffic_s,
                "delay_s": delay_val,
                "length_m": r.length_m,
                "calculated_cost": r.calculated_cost,
                "ml_predicted": r.ml_predicted,
                "congestion_ratio": (r.travel_time_s / r.no_traffic_s) if r.no_traffic_s and r.no_traffic_s > 0 else None
            })
        
        # Calculate statistics
        if analysis_data:
            travel_times = [d["travel_time_s"] for d in analysis_data if d["travel_time_s"]]
            delays = []
            for d in analysis_data:
                delay_val = d.get("delay_s")
                if delay_val is None or delay_val == 0:
                    if d.get("travel_time_s") and d.get("no_traffic_s"):
                        delay_val = max(0, d["travel_time_s"] - d["no_traffic_s"])
                    else:
                        delay_val = 0
                if delay_val > 0:
                    delays.append(delay_val)
            
            costs = [d["calculated_cost"] for d in analysis_data if d.get("calculated_cost")]
            congestion_ratios = [d["congestion_ratio"] for d in analysis_data if d.get("congestion_ratio")]
            
            stats = {
                "avg_travel_time": sum(travel_times) / len(travel_times) if travel_times else 0,
                "avg_delay": sum(delays) / len(delays) if delays else 0,
                "avg_cost": sum(costs) / len(costs) if costs else 0,
                "avg_congestion": sum(congestion_ratios) / len(congestion_ratios) if congestion_ratios else 0,
                "min_travel_time": min(travel_times) if travel_times else 0,
                "max_travel_time": max(travel_times) if travel_times else 0,
                "total_records": len(analysis_data)
            }
        else:
            stats = {}
        
        response_data = {
            "route_id": route_id,
            "route_index": route_index,
            "analysis_data": analysis_data,
            "statistics": stats,
            "latest": analysis_data[0] if analysis_data else None,
            "fetched_at": datetime.now(UTC).isoformat()
        }
        
        response = JSONResponse(content=response_data)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch analysis: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analysis: {str(e)}")


@app.post("/api/refresh-route")
async def refresh_route_analysis(
    request: RouteAnalysisRequest,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Refresh route analysis with latest data from TomTom API.
    Similar to analyze_route but returns data in format suitable for analysis report.
    """
    try:
        # Reuse analyze_route logic
        if isinstance(request.origin, str):
            o_lat, o_lon = tomtom_geocode(request.origin)
            origin_data = {"name": request.origin, "lat": o_lat, "lon": o_lon}
        else:
            o_lat = float(request.origin.get("lat"))
            o_lon = float(request.origin.get("lon"))
            origin_data = request.origin
        
        if isinstance(request.destination, str):
            d_lat, d_lon = tomtom_geocode(request.destination)
            dest_data = {"name": request.destination, "lat": d_lat, "lon": d_lon}
        else:
            d_lat = float(request.destination.get("lat"))
            d_lon = float(request.destination.get("lon"))
            dest_data = request.destination
        
        # Validate coordinates
        if not (-90 <= o_lat <= 90) or not (-180 <= o_lon <= 180):
            raise ValueError("Invalid origin coordinates")
        if not (-90 <= d_lat <= 90) or not (-180 <= d_lon <= 180):
            raise ValueError("Invalid destination coordinates")
        
        route_json = tomtom_route(
            o_lat, o_lon, d_lat, d_lon,
            maxAlternatives=request.maxAlternatives
        )
        
        routes = route_json.get("routes", [])
        if not routes:
            raise HTTPException(status_code=404, detail="No routes found")
        
        analyzed_routes = []
        route_id = f"{origin_data.get('name', f'{o_lat},{o_lon}')}→{dest_data.get('name', f'{d_lat},{d_lon}')}"
        
        for idx, route in enumerate(routes):
            summary = summarize_route(route)
            
            if summary["length_m"] == 0:
                summary["length_m"] = haversine_m(o_lat, o_lon, d_lat, d_lon)
            
            cost = compute_route_cost(
                summary["travel_time_s"],
                summary["no_traffic_s"],
                summary["delay_s"],
                summary["length_m"],
                alpha=request.alpha,
                beta=request.beta,
                gamma=request.gamma
            )
            
            ml_predicted = predict_congestion({
                "distance_km": summary["length_m"] / 1000.0,
                "route_index": idx,
                "travel_time_s": summary["travel_time_s"],
                "no_traffic_s": summary["no_traffic_s"],
                "delay_s": summary["delay_s"]
            })
            
            congestion_ratio = (
                summary["travel_time_s"] / summary["no_traffic_s"]
                if summary["no_traffic_s"] and summary["no_traffic_s"] > 0
                else None
            )
            
            calculated_delay = 0
            if summary["travel_time_s"] and summary["no_traffic_s"]:
                calculated_delay = max(0, summary["travel_time_s"] - summary["no_traffic_s"])
            elif summary.get("delay_s"):
                calculated_delay = summary["delay_s"]
            
            analyzed_route = {
                "route_index": idx,
                "travel_time_s": summary["travel_time_s"],
                "no_traffic_s": summary["no_traffic_s"],
                "delay_s": calculated_delay,
                "length_m": summary["length_m"],
                "congestion_ratio": congestion_ratio,
                "calculated_cost": cost,
                "ml_predicted_congestion": ml_predicted
            }
            analyzed_routes.append(analyzed_route)
            
            # Save to database
            try:
                session = get_session()
                save_analysis(session, {
                    "route_id": f"{route_id}_route{idx}",
                    "origin": origin_data,
                    "destination": dest_data,
                    "travel_time_s": summary["travel_time_s"],
                    "no_traffic_s": summary["no_traffic_s"],
                    "delay_s": summary["delay_s"],
                    "length_m": summary["length_m"],
                    "calculated_cost": cost,
                    "ml_predicted": ml_predicted,
                    "raw_json": route,
                    "user_id": current_user.id if current_user else None
                })
                session.close()
            except Exception as e:
                logger.error(f"Database save error: {e}")
        
        best_route = min(analyzed_routes, key=lambda x: x["calculated_cost"])
        
        return {
            "origin": origin_data,
            "destination": dest_data,
            "route_id": route_id,
            "analyzed_routes": analyzed_routes,
            "best_route_index": best_route["route_index"],
            "best_route": best_route,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Route refresh error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Route refresh failed: {str(e)}")


# ============================================================================
# USER AUTHENTICATION & MANAGEMENT
# ============================================================================

@app.post("/api/auth/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: Session = Depends(get_session)):
    """Register a new user."""
    try:
        if len(user_data.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long"
            )
        
        MAX_PASSWORD_LENGTH = 10000
        if len(user_data.password) > MAX_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password is too long. Maximum {MAX_PASSWORD_LENGTH} characters allowed."
            )
        
        user = create_user(db, AuthUserCreate(**user_data.dict()))
        return UserResponse.model_validate(user)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "password" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password validation error: {error_msg}"
            )
        raise HTTPException(status_code=500, detail=f"Registration failed: {error_msg}")


@app.post("/api/auth/login", response_model=Token)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_session),
    *,
    response: Response,
):
    """Login and get access token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30 * 24 * 60)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
        path="/",
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/police/dashboard", response_class=HTMLResponse)
async def police_dashboard(request: Request, current_user: dict = Depends(require_role("police_supervisor"))):
    """Render the police supervisor dashboard for the user's district."""
    district_id = current_user.get("district_id")
    incidents = _load_police_incidents(district_id)
    district_summary = _build_district_summary(incidents)
    ml_predictions = _predict_police_hotspots(district_id, incidents)
    district_info = DISTRICT_LOCATIONS.get(district_id, {"name": district_id or "Unknown District"})

    return templates.TemplateResponse(
        "police_dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "district_id": district_id,
            "district_info": district_info,
            "incidents": incidents,
            "district_summary": district_summary,
            "ml_predictions": ml_predictions,
        },
    )


@app.get("/police/export/pptx")
async def police_export_pptx(current_user: dict = Depends(require_role("police_supervisor"))):
    """Generate a police supervisor shift report as a PPTX file."""
    try:
        from io import BytesIO
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.enum.shapes import MSO_SHAPE

        district_id = current_user.get("district_id")
        officer_name = current_user.get("username", "Unknown Officer")

        incidents = _load_police_incidents(district_id)
        district_summary = _build_district_summary(incidents)
        ml_predictions = _predict_police_hotspots(district_id, incidents)
        district_info = DISTRICT_LOCATIONS.get(district_id, {"name": district_id or "Unknown District"})

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        title_layout = prs.slide_layouts[0]
        title_body_layout = prs.slide_layouts[5]

        # Slide 1 - Shift summary
        slide1 = prs.slides.add_slide(title_layout)
        slide1.shapes.title.text = "Police Shift Summary"
        slide1.placeholders[1].text = (
            f"District: {district_info.get('name', district_id or 'Unknown District')}\n"
            f"Date: {datetime.now(UTC).strftime('%Y-%m-%d')}\n"
            f"Officer: {officer_name}\n"
            f"Total Incidents: {len(incidents)}"
        )

        # Slide 2 - Incidents table
        slide2 = prs.slides.add_slide(title_body_layout)
        slide2.shapes.title.text = "Incident Breakdown"
        rows = max(len(incidents), 1) + 1
        cols = 4
        table_shape = slide2.shapes.add_table(rows, cols, Inches(0.5), Inches(1.4), Inches(12.3), Inches(5.6))
        table = table_shape.table
        headers = ["ID", "Description", "Severity", "Start Time"]
        for index, header in enumerate(headers):
            table.cell(0, index).text = header
        for row_index, incident in enumerate(incidents, start=1):
            table.cell(row_index, 0).text = _safe_ppt_text(incident.get("id"))
            table.cell(row_index, 1).text = _safe_ppt_text(incident.get("description"))
            table.cell(row_index, 2).text = _safe_ppt_text(incident.get("severity"))
            table.cell(row_index, 3).text = _format_ppt_timestamp(incident.get("start_time"))

        # Slide 3 - ML highlights
        slide3 = prs.slides.add_slide(title_body_layout)
        slide3.shapes.title.text = "ML Prediction Highlights"
        text_box = slide3.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(12), Inches(5.8))
        text_frame = text_box.text_frame
        if ml_predictions:
            for index, prediction in enumerate(ml_predictions, start=1):
                paragraph = text_frame.paragraphs[0] if index == 1 else text_frame.add_paragraph()
                paragraph.text = (
                    f"{index}. {prediction['location']} | "
                    f"Likelihood: {prediction['likelihood_score']}% | "
                    f"Confidence: {prediction['confidence']}% | "
                    f"Type: {prediction['predicted_type']}"
                )
                for run in paragraph.runs:
                    run.font.size = Pt(18)
        else:
            text_frame.text = "No ML predictions available for this district."

        # Slide 4 - Map placeholder
        slide4 = prs.slides.add_slide(title_body_layout)
        slide4.shapes.title.text = "Map Screenshot Placeholder"
        placeholder = slide4.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(1.1), Inches(1.6), Inches(11.2), Inches(4.6)
        )
        placeholder.text_frame.text = (
            "Insert map screenshot here before final delivery.\n\n"
            f"District: {district_info.get('name', district_id or 'Unknown District')}\n"
            f"Incidents on map: {len(incidents)}"
        )

        output = BytesIO()
        prs.save(output)
        output.seek(0)

        filename = f"ShiftReport_District{district_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.pptx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"PPTX export dependency missing: {exc}")
    except Exception as exc:
        logger.error(f"Police PPTX export failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PPTX: {exc}")


@app.post("/auth/login", response_model=RoleToken)
async def role_login(
    login_data: RoleLoginRequest,
    db: Session = Depends(get_session),
    *,
    response: Response,
):
    """Login with an explicit role and return a role-aware JWT."""
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = login_data.role
    district_id = login_data.district_id
    fleet_zone = login_data.fleet_zone

    if role == UserRole.admin and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    if role == UserRole.police_supervisor and not district_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="district_id is required for police_supervisor login",
        )

    if role == UserRole.logistics_manager and not fleet_zone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fleet_zone is required for logistics_manager login",
        )

    access_token = create_role_access_token(
        username=user.username,
        role=role,
        district_id=district_id,
        fleet_zone=fleet_zone,
        expires_delta=timedelta(minutes=30 * 24 * 60),
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
        path="/",
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": role,
        "district_id": district_id,
        "fleet_zone": fleet_zone,
    }


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return UserResponse.model_validate(current_user)


# ============================================================================
# SAVED ROUTES
# ============================================================================

@app.post("/api/saved-routes")
@handle_db_errors
async def create_saved_route(
    route_data: SavedRouteCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session)
):
    """Save a route for the current user."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please login to save routes."
        )
    
    origin_str = json.dumps(route_data.origin) if isinstance(route_data.origin, dict) else route_data.origin
    dest_str = json.dumps(route_data.destination) if isinstance(route_data.destination, dict) else route_data.destination
    
    saved_route = SavedRoute(
        user_id=current_user.id,
        route_name=route_data.route_name,
        origin=origin_str,
        destination=dest_str,
        route_preferences=route_data.route_preferences,
        is_favorite=False,
        share_token=secrets.token_urlsafe(16)
    )
    db.add(saved_route)
    db.commit()
    db.refresh(saved_route)
    return saved_route


@app.get("/api/saved-routes")
@handle_db_errors
async def get_saved_routes(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session),
    favorites_only: bool = Query(False)
):
    """Get saved routes for current user."""
    if not current_user:
        return []
    query = db.query(SavedRoute).filter(SavedRoute.user_id == current_user.id)
    if favorites_only:
        query = query.filter(SavedRoute.is_favorite == True)
    routes = query.order_by(SavedRoute.last_used.desc()).all()
    return routes


@app.put("/api/saved-routes/{route_id}/favorite")
@handle_db_errors
async def toggle_favorite(
    route_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session)
):
    """Toggle favorite status of a saved route."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required for this feature")
    route = db.query(SavedRoute).filter(
        SavedRoute.id == route_id,
        SavedRoute.user_id == current_user.id
    ).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    route.is_favorite = not route.is_favorite
    db.commit()
    return {"is_favorite": route.is_favorite}


@app.delete("/api/saved-routes/{route_id}")
@handle_db_errors
async def delete_saved_route(
    route_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session)
):
    """Delete a saved route."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required for this feature")
    route = db.query(SavedRoute).filter(
        SavedRoute.id == route_id,
        SavedRoute.user_id == current_user.id
    ).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    db.delete(route)
    db.commit()
    return {"message": "Route deleted"}


@app.get("/api/share-route/{share_token}")
@handle_db_errors
async def get_shared_route(share_token: str, db: Session = Depends(get_session)):
    """Get a shared route by token."""
    route = db.query(SavedRoute).filter(SavedRoute.share_token == share_token).first()
    if not route:
        raise HTTPException(status_code=404, detail="Shared route not found")
    return route


# ============================================================================
# ADVANCED ANALYTICS
# ============================================================================

@app.get("/api/analytics/peak-hours/{route_id}")
async def get_peak_hours(
    route_id: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_session)
):
    """Get peak hours analysis for a route."""
    return get_peak_hours_analysis(db, route_id, days)


@app.get("/api/analytics/day-of-week/{route_id}")
async def get_day_analysis(
    route_id: str,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_session)
):
    """Get day of week analysis."""
    return get_day_of_week_analysis(db, route_id, days)


@app.get("/api/analytics/seasonal/{route_id}")
async def get_seasonal_analysis(
    route_id: str,
    months: int = Query(12, ge=1, le=24),
    db: Session = Depends(get_session)
):
    """Get seasonal trends."""
    return get_seasonal_trends(db, route_id, months)


@app.get("/api/analytics/reliability/{route_id}")
async def get_reliability(
    route_id: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_session)
):
    """Get route reliability score."""
    return calculate_route_reliability(db, route_id, days)


@app.get("/api/analytics/predict/{route_id}")
async def get_prediction(
    route_id: str,
    hours_ahead: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_session)
):
    """Predict future congestion."""
    return predict_future_congestion(db, route_id, hours_ahead)


@app.get("/api/analytics/hotspots")
async def get_hotspots(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_session)
):
    """Get traffic hotspots."""
    return get_traffic_hotspots(db, days)


# ============================================================================
# EXPORT & REPORTING
# ============================================================================

@app.get("/api/export/csv/{route_id}")
async def export_csv(
    route_id: str,
    db: Session = Depends(get_session)
):
    """Export route data to CSV."""
    csv_content = export_to_csv(db, route_id)
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=route_{route_id}_{datetime.now(UTC).strftime('%Y%m%d')}.csv"}
    )


@app.get("/api/export/excel/{route_id}")
async def export_excel(
    route_id: str,
    db: Session = Depends(get_session)
):
    """Export route data to Excel."""
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        export_to_excel(db, route_id, tmp.name)
        return FileResponse(
            tmp.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"route_{route_id}_{datetime.now(UTC).strftime('%Y%m%d')}.xlsx"
        )


@app.get("/api/export/pdf/{route_id}")
async def export_pdf(
    route_id: str,
    db: Session = Depends(get_session)
):
    """Export route data to PDF."""
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        export_to_pdf(db, route_id, tmp.name)
        return FileResponse(
            tmp.name,
            media_type="application/pdf",
            filename=f"route_{route_id}_{datetime.now(UTC).strftime('%Y%m%d')}.pdf"
        )


# ============================================================================
# NOTIFICATIONS
# ============================================================================

@app.get("/api/notifications")
@handle_db_errors
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session)
):
    """Get user notifications."""
    if not current_user:
        return []
    return get_user_notifications(db, current_user.id, unread_only, limit)


@app.put("/api/notifications/{notification_id}/read")
@handle_db_errors
async def mark_read(
    notification_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session)
):
    """Mark notification as read."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")
    success = mark_notification_read(db, notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}


@app.post("/api/notifications/check-alerts")
@handle_db_errors
async def check_alerts(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session)
):
    """Check for traffic alerts on saved routes."""
    if not current_user:
        return {"alerts": 0, "notifications": []}
    alerts = check_traffic_alerts(db, current_user.id)
    return {"alerts": len(alerts), "notifications": alerts}


# ============================================================================
# REAL-TIME FEATURES
# ============================================================================

@app.get("/api/realtime/incidents")
async def get_incidents(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius: int = Query(5000, ge=100, le=50000)
):
    """Get traffic incidents near a location."""
    # Validate coordinates
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail="Invalid latitude")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Invalid longitude")
    
    return get_traffic_incidents(lat, lon, radius)


@app.post("/api/realtime/monitor/{route_id}")
async def monitor_route(
    route_id: str,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session)
):
    """Monitor route for changes."""
    change = monitor_route_changes(db, route_id)
    if change:
        if current_user:
            from notifications import create_notification
            create_notification(
                db, current_user.id, 'traffic_alert',
                f"Route Change: {route_id}",
                f"Route travel time changed by {change['change_percent']}%",
                route_id
            )
    return change or {"message": "No significant changes detected"}


# ============================================================================
# ROUTE RATINGS & SOCIAL
# ============================================================================

@app.post("/api/ratings")
@handle_db_errors
async def create_rating(
    rating_data: RouteRatingCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_session)
):
    """Rate a route."""
    user_id = current_user.id if current_user else None
    rating = RouteRating(
        user_id=user_id,
        route_id=rating_data.route_id,
        rating=rating_data.rating,
        review=rating_data.review
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


@app.get("/api/ratings/{route_id}")
@handle_db_errors
async def get_ratings(route_id: str, db: Session = Depends(get_session)):
    """Get ratings for a route."""
    ratings = db.query(RouteRating).filter(RouteRating.route_id == route_id).all()
    if not ratings:
        return {"average_rating": 0, "count": 0, "ratings": []}
    
    avg_rating = sum(r.rating for r in ratings) / len(ratings)
    return {
        "average_rating": round(avg_rating, 2),
        "count": len(ratings),
        "ratings": ratings
    }


# ============================================================================
# ADMIN DASHBOARD
# ============================================================================

@app.get("/api/admin/stats")
@handle_db_errors
async def get_admin_stats(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_session)
):
    """Get admin statistics (admin only)."""
    total_users = db.query(User).count()
    total_routes = db.query(AnalysisResult).count()
    total_saved_routes = db.query(SavedRoute).count()
    total_ratings = db.query(RouteRating).count()
    
    recent_routes = db.query(AnalysisResult).order_by(AnalysisResult.timestamp.desc()).limit(10).all()
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
    
    return {
        "total_users": total_users,
        "total_route_analyses": total_routes,
        "total_saved_routes": total_saved_routes,
        "total_ratings": total_ratings,
        "cache_stats": get_cache_stats(),
        "recent_activity": {
            "routes": len(recent_routes),
            "new_users": len(recent_users)
        }
    }


@app.get("/api/admin/route-analysis")
async def get_all_route_analyses(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_session),
    filter_period: Optional[str] = Query(None, alias="filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get all route analyses with optional filtering (admin only)."""
    import json
    from datetime import datetime, timedelta, UTC
    
    try:
        # Build query
        query = db.query(AnalysisResult)
        
        # Apply time filter if specified
        if filter_period:
            now = datetime.now(UTC)
            if filter_period == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(AnalysisResult.timestamp >= start_date)
            elif filter_period == "week":
                start_date = now - timedelta(days=7)
                query = query.filter(AnalysisResult.timestamp >= start_date)
            elif filter_period == "month":
                start_date = now - timedelta(days=30)
                query = query.filter(AnalysisResult.timestamp >= start_date)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        routes = query.order_by(AnalysisResult.timestamp.desc()).offset(skip).limit(limit).all()
        
        # Format response
        route_data = []
        for r in routes:
            try:
                origin = json.loads(r.origin) if isinstance(r.origin, str) and r.origin.startswith('{') else {"name": str(r.origin) if r.origin else ""}
                dest = json.loads(r.destination) if isinstance(r.destination, str) and r.destination.startswith('{') else {"name": str(r.destination) if r.destination else ""}
            except:
                origin = {"name": str(r.origin) if r.origin else ""}
                dest = {"name": str(r.destination) if r.destination else ""}
            
            route_name = f"{origin.get('name', '')} → {dest.get('name', '')}"
            
            delay_val = r.delay_s
            if delay_val is None or delay_val == 0:
                if r.travel_time_s and r.no_traffic_s:
                    delay_val = max(0, r.travel_time_s - r.no_traffic_s)
                else:
                    delay_val = 0
            
            route_data.append({
                "id": r.id,
                "route": route_name,
                "route_id": r.route_id,
                "travel_time_s": r.travel_time_s,
                "delay_s": delay_val,
                "length_m": r.length_m,
                "calculated_cost": r.calculated_cost,
                "ml_predicted": r.ml_predicted,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "origin": origin,
                "destination": dest
            })
        
        # Calculate statistics from filtered results
        all_routes_for_stats = query.all()
        
        if all_routes_for_stats:
            travel_times = [r.travel_time_s for r in all_routes_for_stats if r.travel_time_s is not None]
            delays = []
            for r in all_routes_for_stats:
                delay_val = r.delay_s
                if delay_val is None or delay_val == 0:
                    if r.travel_time_s and r.no_traffic_s:
                        delay_val = max(0, r.travel_time_s - r.no_traffic_s)
                    else:
                        delay_val = 0
                if delay_val > 0:
                    delays.append(delay_val)
            costs = [r.calculated_cost for r in all_routes_for_stats if r.calculated_cost is not None]
            
            stats = {
                "total": total_count,
                "avg_travel_time": sum(travel_times) / len(travel_times) if travel_times else 0,
                "avg_delay": sum(delays) / len(delays) if delays else 0,
                "avg_cost": sum(costs) / len(costs) if costs else 0
            }
        else:
            stats = {
                "total": 0,
                "avg_travel_time": 0,
                "avg_delay": 0,
                "avg_cost": 0
            }
        
        return {
            "routes": route_data,
            "stats": stats,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total_count
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching route analyses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch route analyses: {str(e)}")


@app.get("/api/admin/users")
async def get_all_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get all users (admin only)."""
    users = db.query(User).offset(skip).limit(limit).all()
    return [UserResponse.model_validate(u) for u in users]


@app.put("/api/admin/users/{user_id}/activate")
async def toggle_user_status(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_session)
):
    """Activate/deactivate a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    db.commit()
    return {"is_active": user.is_active, "message": f"User {'activated' if user.is_active else 'deactivated'}"}


@app.put("/api/admin/users/{user_id}/admin")
async def toggle_admin_status(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_session)
):
    """Grant/revoke admin privileges (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own admin status")
    
    user.is_admin = not user.is_admin
    db.commit()
    return {"is_admin": user.is_admin, "message": f"Admin privileges {'granted' if user.is_admin else 'revoked'}"}


@app.put("/api/admin/users/{user_id}")
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_session)
):
    """Update user details (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update username if provided
    if user_update.username is not None:
        existing_user = db.query(User).filter(User.username == user_update.username, User.id != user_id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = user_update.username
    
    # Update email if provided
    if user_update.email is not None:
        existing_user = db.query(User).filter(User.email == user_update.email, User.id != user_id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already taken")
        user.email = user_update.email
    
    # Update full name if provided
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    
    # Update active status if provided
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    
    # Update admin status if provided
    if user_update.is_admin is not None:
        if user.id == current_user.id and not user_update.is_admin:
            raise HTTPException(status_code=400, detail="Cannot remove your own admin privileges")
        user.is_admin = user_update.is_admin
    
    # Update password if provided and not empty
    if user_update.password is not None and user_update.password.strip() != "":
        if len(user_update.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        user.hashed_password = get_password_hash(user_update.password)
    
    try:
        db.commit()
        db.refresh(user)
        return UserResponse.model_validate(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


@app.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_session)
):
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


@app.get("/api/user/stats")
@handle_db_errors
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session)
):
    """Get user-specific statistics."""
    saved_routes_count = db.query(SavedRoute).filter(SavedRoute.user_id == current_user.id).count()
    analyses_count = db.query(AnalysisResult).filter(AnalysisResult.user_id == current_user.id).count()
    ratings_count = db.query(RouteRating).filter(RouteRating.user_id == current_user.id).count()
    
    recent_analyses = db.query(AnalysisResult).filter(
        AnalysisResult.user_id == current_user.id
    ).order_by(AnalysisResult.timestamp.desc()).limit(10).all()
    
    return {
        "saved_routes": saved_routes_count,
        "analyses": analyses_count,
        "ratings": ratings_count,
        "recent_analyses": [
            {
                "route_id": r.route_id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "travel_time": r.travel_time_s,
                "cost": r.calculated_cost
            }
            for r in recent_analyses
        ]
    }


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

@app.post("/api/cache/clear")
async def clear_route_cache(
    pattern: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user)
):
    """Clear route cache (admin only)."""
    clear_cache(pattern=pattern)
    return {"message": "Cache cleared"}


@app.get("/api/cache/stats")
async def get_cache_statistics():
    """Get cache statistics."""
    return get_cache_stats()


# ============================================================================
# INTEGRATION ENDPOINTS
# ============================================================================

@app.get("/api/integration/navigation/{route_id}")
@handle_db_errors
async def get_navigation_links(
    route_id: str,
    route_index: int = Query(0),
    db: Session = Depends(get_session)
):
    """Get navigation app links (Google Maps, Waze)."""
    result = db.query(AnalysisResult).filter(
        AnalysisResult.route_id.like(f"{route_id}%")
    ).order_by(AnalysisResult.timestamp.desc()).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Route not found")
    
    try:
        origin = json.loads(result.origin) if result.origin and result.origin.startswith('{') else {"name": result.origin}
        dest = json.loads(result.destination) if result.destination and result.destination.startswith('{') else {"name": result.destination}
    except:
        origin = {"name": result.origin}
        dest = {"name": result.destination}
    
    origin_lat = origin.get('lat', 0)
    origin_lon = origin.get('lon', 0)
    dest_lat = dest.get('lat', 0)
    dest_lon = dest.get('lon', 0)
    
    google_maps = f"https://www.google.com/maps/dir/{origin_lat},{origin_lon}/{dest_lat},{dest_lon}"
    waze = f"https://waze.com/ul?ll={dest_lat},{dest_lon}&navigate=yes"
    
    return {
        "google_maps": google_maps,
        "waze": waze,
        "origin": origin,
        "destination": dest
    }