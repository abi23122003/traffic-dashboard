"""Socket.IO event helpers and /police namespace handlers.

This module provides Socket.IO integration for the Police Command Center, enabling
real-time updates for incidents and officer status changes using the /police namespace.

Key features:
- JWT authentication via HttpOnly cookies
- District-based room management for multi-tenancy
- Event emission for incident_new, incident_updated, and officer_status_changed
- Automatic session management and cleanup

Example usage in app.py:
    from socketio_events import register_police_socketio_handlers, emit_incident_new
    
    register_police_socketio_handlers(sio, logger)
    
    # Emit incident update when incident is created
    await emit_incident_new(sio, district_id, incident_data, actor="supervisor_name")
"""

from __future__ import annotations

from datetime import datetime, UTC
from http.cookies import SimpleCookie
from typing import Any, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt

from .auth import ALGORITHM, SECRET_KEY

POLICE_NAMESPACE = "/police"
POLICE_ROLES = {"police_supervisor", "police_officer"}


def _get_token_from_environ(environ: dict[str, Any]) -> str:
    """Extract JWT token from HTTP cookies in the ASGI environ dict.
    
    Supports both 'token' and 'access_token' cookie names for flexibility.
    
    Args:
        environ: ASGI environ dict from Socket.IO connection
        
    Returns:
        JWT token string if found, empty string otherwise
    """
    cookie_header = str(environ.get("HTTP_COOKIE") or "").strip()
    if not cookie_header:
        return ""

    parsed = SimpleCookie()
    parsed.load(cookie_header)

    token_cookie = parsed.get("token")
    if token_cookie and token_cookie.value:
        return str(token_cookie.value)

    access_cookie = parsed.get("access_token")
    if access_cookie and access_cookie.value:
        return str(access_cookie.value)

    return ""


def authenticate_socket_user(environ: dict[str, Any]) -> dict[str, Any]:
    """Authenticate Socket.IO user connection using JWT token from HttpOnly cookie.
    
    This function:
    1. Extracts JWT from HTTP_COOKIE header (set by HttpOnly cookie)
    2. Validates JWT signature using SECRET_KEY
    3. Verifies user has required police role (supervisor or officer)
    4. Returns user claims for session management
    
    Args:
        environ: ASGI environ dict containing HTTP_COOKIE header
        
    Returns:
        Dict with user claims: username, role, district_id, exp
        
    Raises:
        HTTPException: 401 if token missing/invalid, 403 if insufficient role
        
    Example:
        user = authenticate_socket_user(environ)
        # Returns: {
        #   'username': 'supervisor1',
        #   'role': 'police_supervisor',
        #   'district_id': 'district_1',
        #   'exp': 1234567890
        # }
    """
    token = _get_token_from_environ(environ)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token in cookies",
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    username = payload.get("sub")
    role = payload.get("role")
    district_id = payload.get("district_id")

    if not username or role not in POLICE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: police role required (found: {role})",
        )

    return {
        "username": username,
        "role": role,
        "district_id": district_id,
        "exp": payload.get("exp"),
    }


def register_police_socketio_handlers(sio: Any, logger: Any) -> None:
    """Register all Socket.IO event handlers for the police /police namespace.
    
    Sets up:
    - connect/disconnect handlers with JWT authentication
    - district-based room management
    - join_district event for dynamic room joining
    
    This creates an authenticated WebSocket connection that enforces:
    - Police role validation (supervisor or officer)
    - District-level isolation (officers can't access other districts)
    - Automatic room assignment based on JWT district_id
    
    Args:
        sio: AsyncServer instance from socketio.AsyncServer()
        logger: Logger instance for debug/warning output
        
    Example:
        from socketio_events import register_police_socketio_handlers
        import socketio
        
        sio = socketio.AsyncServer(async_mode='asgi')
        register_police_socketio_handlers(sio, logger)
    """
    @sio.event(namespace=POLICE_NAMESPACE)
    async def connect(sid, environ, auth):
        """Handle new Socket.IO connection with JWT authentication.
        
        Validates JWT, saves session, and adds client to district room.
        
        Args:
            sid: Socket ID (unique per connection)
            environ: ASGI environ dict with HTTP_COOKIE
            auth: Optional auth dict from client (not used, cookie is primary)
            
        Returns:
            False to reject connection, None/True to accept
        """
        try:
            user_claims = authenticate_socket_user(environ)
        except HTTPException as exc:
            logger.warning(
                "Socket.IO auth rejected sid=%s: %s (HTTP status: %s)",
                sid,
                exc.detail,
                exc.status_code,
            )
            # Return False to close connection - client will see error in browser console
            return False
        except Exception as exc:
            logger.error(
                "Socket.IO auth error sid=%s: %s",
                sid,
                str(exc),
            )
            return False

        await sio.save_session(sid, user_claims, namespace=POLICE_NAMESPACE)
        district_id = str(user_claims.get("district_id") or "").strip()
        if district_id:
            await sio.enter_room(sid, district_id, namespace=POLICE_NAMESPACE)

        logger.info(
            "Socket.IO police connected sid=%s user=%s role=%s district=%s",
            sid,
            user_claims.get("username"),
            user_claims.get("role"),
            district_id or "none",
        )

    @sio.event(namespace=POLICE_NAMESPACE)
    async def disconnect(sid):
        """Handle Socket.IO disconnection cleanup.
        
        Args:
            sid: Socket ID being disconnected
        """
        logger.info("Socket.IO police disconnected sid=%s", sid)

    @sio.on("join_district", namespace=POLICE_NAMESPACE)
    async def join_district_room(sid, data):
        """Handle dynamic district room joining.
        
        Client can emit this event to join their district's room for broadcasts.
        Validates that requested district matches JWT district (prevents cross-district access).
        
        Args:
            sid: Socket ID
            data: Dict with 'district_id' key
        """
        session = await sio.get_session(sid, namespace=POLICE_NAMESPACE)
        session_district = str((session or {}).get("district_id") or "").strip()
        requested_district = str((data or {}).get("district_id") or "").strip()

        if not session_district:
            logger.warning("join_district called for sid=%s with no session district", sid)
            return

        # Restrict clients to their JWT district even if a different district is requested.
        target_district = session_district if requested_district != session_district else requested_district
        await sio.enter_room(sid, target_district, namespace=POLICE_NAMESPACE)
        logger.debug("sid=%s joined district room=%s", sid, target_district)


async def emit_incident_new(
    sio: Any,
    district_id: str,
    incident: dict[str, Any],
    *,
    actor: Optional[str] = None,
) -> None:
    """Broadcast new incident event to all supervisors in a district.
    
    Called when a new incident is created (POST /api/incident/new).
    
    Args:
        sio: AsyncServer instance
        district_id: Target district for broadcast
        incident: Incident data dict with at least 'id' key
        actor: Username of supervisor who created the incident
        
    Example:
        await emit_incident_new(
            sio,
            "district_1",
            {"id": "incident-123", "severity": "high", "description": "..."},
            actor="supervisor_name"
        )
    """
    await sio.emit(
        "incident_new",
        {
            "district_id": district_id,
            "incident": incident,
            "actor": actor,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        room=district_id,
        namespace=POLICE_NAMESPACE,
    )


async def emit_incident_updated(
    sio: Any,
    district_id: str,
    incident: dict[str, Any],
    *,
    update_type: str,
    actor: Optional[str] = None,
) -> None:
    """Broadcast incident update event to all supervisors in a district.
    
    Called when incident status changes (dispatched, resolved, etc).
    
    Args:
        sio: AsyncServer instance
        district_id: Target district for broadcast
        incident: Incident data dict
        update_type: Type of update (e.g., 'dispatched', 'resolved')
        actor: Username of supervisor who made the change
        
    Example:
        await emit_incident_updated(
            sio,
            "district_1",
            {"id": "incident-123", "status": "resolved"},
            update_type="resolved",
            actor="supervisor_name"
        )
    """
    await sio.emit(
        "incident_updated",
        {
            "district_id": district_id,
            "update_type": update_type,
            "incident": incident,
            "actor": actor,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        room=district_id,
        namespace=POLICE_NAMESPACE,
    )


async def emit_officer_status_changed(
    sio: Any,
    district_id: str,
    officer: dict[str, Any],
    *,
    actor: Optional[str] = None,
) -> None:
    """Broadcast officer status change event to all supervisors in a district.
    
    Called when officer is dispatched or returns (becomes available).
    
    Args:
        sio: AsyncServer instance
        district_id: Target district for broadcast
        officer: Officer data dict with at least 'id' and 'status' keys
        actor: Username of supervisor who made the change
        
    Example:
        await emit_officer_status_changed(
            sio,
            "district_1",
            {"id": "officer_123", "status": "available", "name": "Officer Smith"},
            actor="supervisor_name"
        )
    """
    await sio.emit(
        "officer_status_changed",
        {
            "district_id": district_id,
            "officer": officer,
            "actor": actor,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        room=district_id,
        namespace=POLICE_NAMESPACE,
    )


async def emit_officer_dispatched(
    sio: Any,
    district_id: str,
    dispatch_data: dict[str, Any],
    *,
    actor: Optional[str] = None,
) -> None:
    """Broadcast officer dispatch event to all supervisors in a district.
    
    Called when an officer is dispatched to a specific incident.
    Contains dispatch details for real-time dashboard updates.
    
    Args:
        sio: AsyncServer instance
        district_id: Target district for broadcast
        dispatch_data: Dispatch details dict with:
            - dispatch_id: Dispatch log record ID
            - officer_id: Officer/unit ID
            - incident_id: Incident ID
            - eta: Estimated time of arrival (optional)
            - supervisor_id: Supervisor who made dispatch
        actor: Username of supervisor who made the dispatch
        
    Example:
        await emit_officer_dispatched(
            sio,
            "district_1",
            {
                "dispatch_id": 42,
                "officer_id": "unit_001",
                "incident_id": "incident_123",
                "eta": 5,
                "supervisor_id": "sup_001"
            },
            actor="supervisor_name"
        )
    """
    await sio.emit(
        "officer_dispatched",
        {
            "district_id": district_id,
            "dispatch": dispatch_data,
            "actor": actor,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        room=district_id,
        namespace=POLICE_NAMESPACE,
    )
