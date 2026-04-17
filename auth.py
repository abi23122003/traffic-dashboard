"""
Authentication and user management utilities.
"""

import os
import hashlib
from enum import Enum
from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from db import get_session, User
from logging_config import get_logger

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# Password hashing
# Configure to handle bcrypt's 72-byte limit gracefully
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",  # Use bcrypt 2b format
    bcrypt__rounds=12,   # Number of rounds
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str


class UserRole(str, Enum):
    user = "user"
    admin = "admin"
    police_supervisor = "police_supervisor"
    logistics_manager = "logistics_manager"


class RoleLoginRequest(BaseModel):
    username: str
    password: str
    role: UserRole
    district_id: Optional[str] = None
    fleet_zone: Optional[str] = None


class RoleToken(BaseModel):
    access_token: str
    token_type: str
    role: UserRole
    district_id: Optional[str] = None
    fleet_zone: Optional[str] = None


class TokenData(BaseModel):
    username: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    department: str = "general"


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    department: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


def _preprocess_password(password: str) -> str:
    """
    Preprocess password to handle bcrypt's 72-byte limit.
    For passwords longer than 72 bytes, we use SHA256 to hash them first,
    then pass the hash to bcrypt. This allows passwords of any length.
    
    Returns a string that when encoded to bytes is guaranteed to be <= 72 bytes.
    """
    # Convert password to bytes to check actual byte length
    password_bytes = password.encode('utf-8')
    
    # If password is 72 bytes or less, use it directly
    if len(password_bytes) <= 72:
        return password
    
    # For longer passwords, hash with SHA256 first
    # Use hexdigest() which produces a 64-character hex string (32 bytes when encoded)
    # This is well under the 72-byte limit
    sha256_hash = hashlib.sha256(password_bytes).hexdigest()
    return sha256_hash


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    Handles both short passwords (direct bcrypt) and long passwords (SHA256 + bcrypt).
    """
    # Preprocess the password the same way it was hashed
    processed_password = _preprocess_password(plain_password)
    
    # Ensure the processed password is <= 72 bytes
    processed_bytes = processed_password.encode('utf-8')
    if len(processed_bytes) > 72:
        password_bytes = plain_password.encode('utf-8')
        processed_password = hashlib.sha256(password_bytes).hexdigest()
        processed_bytes = processed_password.encode('utf-8')
    
    # Use bcrypt directly to avoid passlib's backend detection issues
    try:
        import bcrypt
        password_bytes = processed_password.encode('utf-8')
        # Ensure it's <= 72 bytes
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except ImportError:
        # Fallback to passlib if bcrypt not available
        try:
            return pwd_context.verify(processed_password, hashed_password)
        except Exception:
            # Try direct verification as fallback
            try:
                return pwd_context.verify(plain_password, hashed_password)
            except:
                return False
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    For passwords longer than 72 bytes, we pre-hash with SHA256 first.
    This allows passwords of virtually any length while maintaining security.
    """
    # Always preprocess password to ensure it's <= 72 bytes
    processed_password = _preprocess_password(password)
    
    # Ensure the processed password is definitely <= 72 bytes
    processed_bytes = processed_password.encode('utf-8')
    if len(processed_bytes) > 72:
        # If somehow still too long, force SHA256
        password_bytes = password.encode('utf-8')
        processed_password = hashlib.sha256(password_bytes).hexdigest()
    
    # Hash with passlib/bcrypt
    # Use bcrypt directly to avoid passlib's backend detection issues
    try:
        import bcrypt
        # Generate salt
        salt = bcrypt.gensalt(rounds=12)
        # Hash the password
        password_bytes = processed_password.encode('utf-8')
        # Ensure it's <= 72 bytes
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        hashed = bcrypt.hashpw(password_bytes, salt)
        # Return as string (passlib format)
        return hashed.decode('utf-8')
    except ImportError:
        # Fallback to passlib if bcrypt not available
        try:
            return pwd_context.hash(processed_password)
        except ValueError as e:
            error_msg = str(e).lower()
            if "72" in error_msg or "truncate" in error_msg or "longer" in error_msg:
                # Force SHA256 pre-hashing
                password_bytes = password.encode('utf-8')
                sha256_hash = hashlib.sha256(password_bytes).hexdigest()
                return pwd_context.hash(sha256_hash)
            raise


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_role_access_token(
    username: str,
    role: UserRole,
    district_id: Optional[str] = None,
    fleet_zone: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token with role-based claims."""
    claims = {
        "sub": username,
        "role": role.value,
    }
    if district_id is not None:
        claims["district_id"] = district_id
    if fleet_zone is not None:
        claims["fleet_zone"] = fleet_zone
    return create_access_token(claims, expires_delta=expires_delta)


def require_role(required_role: str):
    """Return a FastAPI dependency that enforces a specific JWT role."""

    async def _role_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient role",
            )
        return current_user

    return _role_dependency


def require_police_department_user():
    """Return a FastAPI dependency that only allows police-department users."""

    async def _police_department_dependency(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_session),
    ) -> dict:
        if current_user.get("role") != UserRole.police_supervisor.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: police supervisor role required",
            )

        user = get_user_by_username(db, current_user.get("username", ""))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if (getattr(user, "department", None) or "").strip().lower() != "police":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Police department access required",
            )

        return current_user

    return _police_department_dependency


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user by username or email."""
    # Try username first
    user = get_user_by_username(db, username)
    
    # If not found by username, try email
    if not user:
        user = get_user_by_email(db, username)
    
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def create_user(db: Session, user_data: UserCreate) -> User:
    """Create a new user."""
    # Validate minimum password length
    if len(user_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    # Maximum password length check (reasonable limit to prevent abuse)
    # We now support passwords of any length via SHA256 pre-hashing
    # But we set a reasonable maximum to prevent abuse (e.g., 10,000 characters)
    MAX_PASSWORD_LENGTH = 10000
    if len(user_data.password) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password is too long. Maximum {MAX_PASSWORD_LENGTH} characters allowed."
        )
    
    # Check if user exists
    if get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        department=(user_data.department or "general").strip().lower(),
        is_active=True,
        is_admin=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


async def get_current_db_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_session)
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except ExpiredSignatureError:
        raise
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    
    # Update last login
    user.last_login = datetime.now(UTC)
    db.commit()
    
    return user


async def get_current_user(request: Request) -> dict:
    """Decode a Bearer token and return the JWT payload."""
    authorization = request.headers.get("Authorization", "")
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    else:
        token = (
            request.query_params.get("token")
            or request.query_params.get("access_token")
            or request.cookies.get("access_token")
            or request.cookies.get("token")
            or ""
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "username": username,
        "role": role,
        "district_id": payload.get("district_id"),
        "fleet_zone": payload.get("fleet_zone"),
        "exp": payload.get("exp"),
    }


async def get_current_active_user(
    current_user: User = Depends(get_current_db_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current admin user."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def get_optional_user(
    request: Request,
    db: Session = Depends(get_session)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None (for optional auth)."""
    # Try to get token from Authorization header manually
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = get_user_by_username(db, username=username)
        return user if user and user.is_active else None
    except (JWTError, Exception):
        return None


def ensure_admin_user_exists(db: Session) -> User:
    """
    Ensure the default admin user (Admin/Admin123) exists in the database.
    Creates it if it doesn't exist, or updates password if it exists but password is wrong.
    """
    logger = get_logger(__name__)
    admin_username = "Admin"
    admin_password = "Admin123"
    admin_email = "admin@trafficdashboard.com"
    
    # Check if admin user exists
    admin_user = get_user_by_username(db, admin_username)
    
    if admin_user:
        # Admin exists, verify password is correct
        if not verify_password(admin_password, admin_user.hashed_password):
            # Password doesn't match, update it
            admin_user.hashed_password = get_password_hash(admin_password)
            admin_user.is_admin = True
            admin_user.is_active = True
            admin_user.department = "admin"
            db.commit()
            db.refresh(admin_user)
            logger.info(f"✅ Updated admin user password for {admin_username}")
        elif not admin_user.is_admin:
            # User exists but is not admin, make them admin
            admin_user.is_admin = True
            admin_user.is_active = True
            admin_user.department = "admin"
            db.commit()
            db.refresh(admin_user)
            logger.info(f"✅ Updated user {admin_username} to admin")
        return admin_user
    else:
        # Admin doesn't exist, create it
        hashed_password = get_password_hash(admin_password)
        admin_user = User(
            username=admin_username,
            email=admin_email,
            hashed_password=hashed_password,
            full_name="Administrator",
            department="admin",
            is_active=True,
            is_admin=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        logger.info(f"✅ Created default admin user: {admin_username}")
        return admin_user