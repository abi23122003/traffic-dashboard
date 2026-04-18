"""Socket.IO event helpers and /police namespace handlers."""

from __future__ import annotations

from datetime import datetime, UTC
from http.cookies import SimpleCookie
from typing import Any, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt

from auth import ALGORITHM, SECRET_KEY

POLICE_NAMESPACE = "/police"
POLICE_ROLES = {"police_supervisor", "police_officer"}


def _get_token_from_environ(environ: dict[str, Any]) -> str:
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
    token = _get_token_from_environ(environ)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    username = payload.get("sub")
    role = payload.get("role")
    district_id = payload.get("district_id")

    if not username or role not in POLICE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: police role required",
        )

    return {
        "username": username,
        "role": role,
        "district_id": district_id,
        "exp": payload.get("exp"),
    }


def register_police_socketio_handlers(sio: Any, logger: Any) -> None:
    @sio.event(namespace=POLICE_NAMESPACE)
    async def connect(sid, environ, auth):
        try:
            user_claims = authenticate_socket_user(environ)
        except HTTPException as exc:
            logger.warning("Socket.IO auth rejected sid=%s: %s", sid, exc.detail)
            return False

        await sio.save_session(sid, user_claims, namespace=POLICE_NAMESPACE)
        district_id = str(user_claims.get("district_id") or "").strip()
        if district_id:
            await sio.enter_room(sid, district_id, namespace=POLICE_NAMESPACE)

        logger.info(
            "Socket.IO police connected sid=%s user=%s district=%s",
            sid,
            user_claims.get("username"),
            district_id or "-",
        )

    @sio.event(namespace=POLICE_NAMESPACE)
    async def disconnect(sid):
        logger.info("Socket.IO police disconnected sid=%s", sid)

    @sio.on("join_district", namespace=POLICE_NAMESPACE)
    async def join_district_room(sid, data):
        session = await sio.get_session(sid, namespace=POLICE_NAMESPACE)
        session_district = str((session or {}).get("district_id") or "").strip()
        requested_district = str((data or {}).get("district_id") or "").strip()

        if not session_district:
            return

        # Restrict clients to their JWT district even if a different district is requested.
        target_district = session_district if requested_district != session_district else requested_district
        await sio.enter_room(sid, target_district, namespace=POLICE_NAMESPACE)


async def emit_incident_new(
    sio: Any,
    district_id: str,
    incident: dict[str, Any],
    *,
    actor: Optional[str] = None,
) -> None:
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
