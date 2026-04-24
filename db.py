"""
Database persistence layer using SQLAlchemy with PostgreSQL or SQLite fallback.
"""

import os
import json
from datetime import datetime, UTC
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from logging_config import get_logger

logger = get_logger(__name__)

Base = declarative_base()
_ENGINE = None
_SESSION_LOCAL = None

# Database configuration - supports PostgreSQL or SQLite
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
DB_PATH = os.getenv("DB_PATH", "traffic_analysis.db")

# PostgreSQL configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "traffic_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "traffic_dashboard")


class User(Base):
    """User model for authentication and user management."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    department = Column(String(50), nullable=False, default="general")
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    saved_routes = relationship("SavedRoute", back_populates="user", cascade="all, delete-orphan")
    route_ratings = relationship("RouteRating", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class SavedRoute(Base):
    """Saved/favorite routes for users."""
    __tablename__ = "saved_routes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    route_name = Column(String, nullable=False)
    origin = Column(Text, nullable=False)  # JSON string
    destination = Column(Text, nullable=False)  # JSON string
    route_preferences = Column(JSON, nullable=True)  # Store route options
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_used = Column(DateTime, default=lambda: datetime.now(UTC))
    usage_count = Column(Integer, default=0)
    share_token = Column(String, unique=True, index=True, nullable=True)  # For sharing
    
    # Relationships
    user = relationship("User", back_populates="saved_routes")


class RouteRating(Base):
    """Route ratings and reviews from users."""
    __tablename__ = "route_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Made nullable for anonymous ratings
    route_id = Column(String, nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # Relationships
    user = relationship("User", back_populates="route_ratings")


class Notification(Base):
    """User notifications and alerts."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, nullable=False)  # 'traffic_alert', 'best_time', 'congestion_warning'
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    route_id = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # Relationships
    user = relationship("User", back_populates="notifications")


class PoliceDispatchAssignment(Base):
    """Tracks active police dispatch assignments for supervisor operations."""
    __tablename__ = "police_dispatch_assignments"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(String, nullable=False, index=True)
    incident_id = Column(String, nullable=False, unique=True, index=True)
    unit_id = Column(String, nullable=False, unique=True, index=True)
    assigned_by = Column(String, nullable=False)
    assigned_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    status = Column(String, nullable=False, default="active")


class OfficerDispatchStatus(Base):
    """Tracks latest dispatch status for each officer/unit."""
    __tablename__ = "officer_dispatch_status"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(String, nullable=False, index=True)
    officer_id = Column(String, nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default="available", index=True)
    assigned_incident_id = Column(String, nullable=True, index=True)
    mobile_token = Column(String, nullable=True, index=True)  # Firebase device token for push notifications
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True)


class DispatchLog(Base):
    """Immutable dispatch audit trail."""
    __tablename__ = "dispatch_log"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(String, nullable=False, index=True)
    incident_id = Column(String, nullable=False, index=True)
    officer_id = Column(String, nullable=False, index=True)
    assigned_by = Column(String, nullable=False)
    assigned_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    status = Column(String(30), nullable=False, default="dispatched", index=True)


class SharedAlert(Base):
    """Sanitized cross-department road-impact alerts for logistics."""
    __tablename__ = "shared_alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(64), nullable=False, unique=True, index=True)
    zone = Column(String(120), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    affected_roads = Column(JSON, nullable=False, default=list)
    expires_at = Column(DateTime, nullable=False, index=True)


class MLFeedback(Base):
    """Resolved-incident training feedback records."""
    __tablename__ = "ml_feedback"

    id = Column(Integer, primary_key=True, index=True)
    incident_type = Column(String(100), nullable=False, index=True)
    zone = Column(String(120), nullable=False, index=True)
    time_of_day = Column(Integer, nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False, index=True)
    response_time_minutes = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    outcome = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)


class MLRetrainAudit(Base):
    """Tracks model retrain runs for supervisor/admin observability."""
    __tablename__ = "ml_retrain_audit"

    id = Column(Integer, primary_key=True, index=True)
    retrained_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    retrained_by = Column(String(120), nullable=False)
    feedback_rows = Column(Integer, nullable=False, default=0)
    export_path = Column(String(255), nullable=True)


class Shift(Base):
    """Tracks police supervisor shifts and operations."""
    __tablename__ = "police_shifts"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(String, nullable=False, index=True)
    supervisor_id = Column(String, nullable=False)
    supervisor_name = Column(String, nullable=False)
    start_time = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="active")
    incidents_count = Column(Integer, default=0)
    officers_on_duty = Column(Integer, default=0)
    notes = Column(Text, nullable=True)


class ShiftAttendance(Base):
    """Tracks officer attendance during shifts."""
    __tablename__ = "shift_attendance"

    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("police_shifts.id"), nullable=False, index=True)
    officer_username = Column(String, nullable=False)
    officer_name = Column(String, nullable=False)
    clock_in_time = Column(DateTime, default=lambda: datetime.now(UTC))
    clock_out_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="present")


class OfficerIncidentCount(Base):
    """Tracks incidents handled by each officer during their shift."""
    __tablename__ = "officer_incident_counts"

    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("police_shifts.id"), nullable=False, index=True)
    officer_username = Column(String, nullable=False, index=True)
    officer_name = Column(String, nullable=False)
    incident_count_critical = Column(Integer, default=0)  # Critical incidents
    incident_count_high = Column(Integer, default=0)      # High severity
    incident_count_medium = Column(Integer, default=0)    # Medium severity
    incident_count_low = Column(Integer, default=0)       # Low severity
    needs_rotation = Column(Boolean, default=False)       # True if 3+ critical incidents
    last_updated = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class AnalysisResult(Base):
    """SQLAlchemy model for analysis results table."""
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    route_id = Column(String, index=True)
    origin = Column(String)  # JSON string or text
    destination = Column(String)  # JSON string or text
    travel_time_s = Column(Float)
    no_traffic_s = Column(Float)
    delay_s = Column(Float)
    length_m = Column(Float)
    calculated_cost = Column(Float)
    ml_predicted = Column(Float, nullable=True)
    raw_json = Column(Text, nullable=True)  # Store full route JSON if needed
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Optional user association
    hour_of_day = Column(Integer, nullable=True, index=True)  # For analytics
    day_of_week = Column(Integer, nullable=True, index=True)  # 0=Monday, 6=Sunday
    month = Column(Integer, nullable=True, index=True)  # For seasonal analysis


def get_engine():
    """
    Create and return SQLAlchemy engine.
    Supports PostgreSQL (production) or SQLite (development).
    """
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    if DB_TYPE == "postgresql" or DB_TYPE == "postgres":
        # PostgreSQL connection string
        if not POSTGRES_PASSWORD:
            logger.warning("PostgreSQL password not set, falling back to SQLite")
            return _get_sqlite_engine()
        
        database_url = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
            f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        )
        try:
            engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,  # Verify connections before using
                echo=False  # Set to True for SQL query logging
            )
            # Test connection
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            logger.info(f"✅ Connected to PostgreSQL database: {POSTGRES_DB}")
            _ENGINE = engine
            return _ENGINE
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            logger.info("Falling back to SQLite")
            return _get_sqlite_engine()
    else:
        # SQLite (default for development)
        return _get_sqlite_engine()


def _get_sqlite_engine():
    """Create SQLite engine."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    logger.info(f"Using SQLite database: {DB_PATH}")
    _ENGINE = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
        echo=False
    )
    return _ENGINE


def _ensure_user_department_column(engine):
    """Add the users.department column if it does not exist yet."""
    inspector = inspect(engine)
    try:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
    except Exception:
        return

    if "department" not in user_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(50) NOT NULL DEFAULT 'general'"))

    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET department = COALESCE(NULLIF(department, ''), 'general')"))


def get_session() -> Session:
    """Create and return a database session."""
    global _SESSION_LOCAL
    if _SESSION_LOCAL is None:
        engine = get_engine()
        _SESSION_LOCAL = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SESSION_LOCAL()


def get_db():
    """FastAPI dependency that guarantees per-request session cleanup."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Initialize database tables."""
    try:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        _ensure_user_department_column(engine)
        logger.info("✅ Database tables initialized successfully")
        
        # Ensure default admin user exists
        try:
            from auth import ensure_admin_user_exists, ensure_police_user_exists
            session = get_session()
            ensure_admin_user_exists(session)
            ensure_police_user_exists(session)
            session.execute(text("UPDATE users SET department = 'admin' WHERE is_admin = 1"))
            session.commit()
            session.close()
            logger.info("✅ Default admin user verified/created")
        except Exception as e:
            logger.warning(f"⚠️ Could not create default admin user: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise


def save_analysis(session: Session, analysis_object: dict) -> AnalysisResult:
    """
    Save an analysis result to the database.
    
    Args:
        session: SQLAlchemy session
        analysis_object: Dictionary with analysis data containing:
            - route_id: str
            - origin: str or dict
            - destination: str or dict
            - travel_time_s: float
            - no_traffic_s: float
            - delay_s: float
            - length_m: float
            - calculated_cost: float
            - ml_predicted: float (optional)
            - raw_json: str (optional)
            
    Returns:
        Saved AnalysisResult object
    """
    import json
    
    # Convert origin/destination to string if dict
    origin_str = json.dumps(analysis_object.get("origin")) if isinstance(
        analysis_object.get("origin"), dict
    ) else str(analysis_object.get("origin", ""))
    
    dest_str = json.dumps(analysis_object.get("destination")) if isinstance(
        analysis_object.get("destination"), dict
    ) else str(analysis_object.get("destination", ""))
    
    now = datetime.now(UTC)
    result = AnalysisResult(
        timestamp=now,
        route_id=analysis_object.get("route_id", ""),
        origin=origin_str,
        destination=dest_str,
        travel_time_s=analysis_object.get("travel_time_s"),
        no_traffic_s=analysis_object.get("no_traffic_s"),
        delay_s=analysis_object.get("delay_s", 0),
        length_m=analysis_object.get("length_m", 0),
        calculated_cost=analysis_object.get("calculated_cost"),
        ml_predicted=analysis_object.get("ml_predicted"),
        raw_json=json.dumps(analysis_object.get("raw_json")) if analysis_object.get("raw_json") else None,
        user_id=analysis_object.get("user_id"),
        hour_of_day=now.hour,
        day_of_week=now.weekday(),
        month=now.month
    )
    
    session.add(result)
    session.commit()
    session.refresh(result)
    return result

