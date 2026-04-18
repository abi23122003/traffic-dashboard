"""Mobile app routes for officer auth, status updates, and dispatch actions."""

import logging
import secrets
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

mobile_router = APIRouter(prefix="/api/mobile", tags=["mobile"])
logger = logging.getLogger(__name__)

_context: Dict[str, Any] = {
    "officers": None,
    "incidents": None,
    "dispatches": None,
    "manager": None,
}

_mobile_tokens: Dict[str, Dict[str, Any]] = {}


class MobileLoginRequest(BaseModel):
    officer_id: int


class DeviceTokenRequest(BaseModel):
    officer_id: int
    device_token: str


class OfficerStatusRequest(BaseModel):
    officer_id: int
    status: str = Field(..., min_length=2)
    incident_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class DispatchActionRequest(BaseModel):
    officer_id: int
    incident_id: str
    action: str = Field(..., description="accept | reject | en_route | on_scene | completed")


def configure_mobile_context(
    officers_ref,
    incidents_ref,
    dispatches_ref,
    manager,
) -> None:
    _context["officers"] = officers_ref
    _context["incidents"] = incidents_ref
    _context["dispatches"] = dispatches_ref
    _context["manager"] = manager


def _require_context_ready() -> None:
    if not _context["officers"] or _context["incidents"] is None or _context["dispatches"] is None:
        raise HTTPException(status_code=500, detail="Mobile context not configured")


def _find_officer(officer_id: int) -> Optional[Dict[str, Any]]:
    officers = _context["officers"]
    return next((o for o in officers if int(o.get("id")) == int(officer_id)), None)


def _find_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    incidents = _context["incidents"]
    return next((i for i in incidents if str(i.get("id")) == str(incident_id)), None)


def _get_token_claims(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    claims = _mobile_tokens.get(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid mobile token")
    return claims


@mobile_router.post("/login")
async def mobile_login(payload: MobileLoginRequest):
    _require_context_ready()
    officer = _find_officer(payload.officer_id)
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")

    token = secrets.token_urlsafe(32)
    claims = {
        "officer_id": officer["id"],
        "issued_at": datetime.now(UTC).isoformat(),
    }
    _mobile_tokens[token] = claims

    return {
        "access_token": token,
        "token_type": "bearer",
        "officer": officer,
    }


@mobile_router.post("/device-token")
async def register_device_token(
    payload: DeviceTokenRequest,
    authorization: Optional[str] = Header(default=None),
):
    _require_context_ready()
    claims = _get_token_claims(authorization)
    if int(claims["officer_id"]) != int(payload.officer_id):
        raise HTTPException(status_code=403, detail="Token does not match officer")

    officer = _find_officer(payload.officer_id)
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")

    officer["device_token"] = payload.device_token
    officer["last_ping"] = datetime.now(UTC).isoformat()
    return {"message": "Device token registered"}


@mobile_router.get("/incidents")
async def mobile_incident_list(authorization: Optional[str] = Header(default=None)):
    _require_context_ready()
    _get_token_claims(authorization)
    return _context["incidents"]


@mobile_router.get("/incidents/{incident_id}")
async def mobile_incident_detail(incident_id: str, authorization: Optional[str] = Header(default=None)):
    _require_context_ready()
    _get_token_claims(authorization)
    incident = _find_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@mobile_router.post("/officer/status")
async def update_officer_status(
    payload: OfficerStatusRequest,
    authorization: Optional[str] = Header(default=None),
):
    _require_context_ready()
    claims = _get_token_claims(authorization)
    if int(claims["officer_id"]) != int(payload.officer_id):
        raise HTTPException(status_code=403, detail="Token does not match officer")

    officer = _find_officer(payload.officer_id)
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")

    officer["status"] = payload.status
    officer["last_ping"] = datetime.now(UTC).isoformat()
    if payload.lat is not None:
        officer["lat"] = payload.lat
    if payload.lng is not None:
        officer["lng"] = payload.lng

    if payload.incident_id:
        _context["dispatches"][str(payload.incident_id)] = {
            "officer_id": officer["id"],
            "incident_id": str(payload.incident_id),
            "status": payload.status,
            "updated_at": officer["last_ping"],
        }

    manager = _context["manager"]
    await manager.broadcast({"type": "officer_update", "data": officer})
    await manager.broadcast(
        {
            "type": "dispatch_status_update",
            "data": {
                "officer_id": officer["id"],
                "incident_id": payload.incident_id,
                "status": payload.status,
                "updated_at": officer["last_ping"],
            },
        }
    )

    return {"message": "Officer status updated", "officer": officer}


@mobile_router.post("/dispatch/respond")
async def respond_to_dispatch(
    payload: DispatchActionRequest,
    authorization: Optional[str] = Header(default=None),
):
    _require_context_ready()
    claims = _get_token_claims(authorization)
    if int(claims["officer_id"]) != int(payload.officer_id):
        raise HTTPException(status_code=403, detail="Token does not match officer")

    officer = _find_officer(payload.officer_id)
    incident = _find_incident(payload.incident_id)
    if not officer or not incident:
        raise HTTPException(status_code=404, detail="Officer or incident not found")

    action_to_status = {
        "accept": "accepted",
        "reject": "rejected",
        "en_route": "en-route",
        "on_scene": "on-scene",
        "completed": "completed",
    }
    status_value = action_to_status.get(payload.action)
    if not status_value:
        raise HTTPException(status_code=400, detail="Invalid dispatch action")

    officer["status"] = "occupied" if status_value in {"on-scene", "completed"} else "en-route"
    officer["last_ping"] = datetime.now(UTC).isoformat()

    _context["dispatches"][str(payload.incident_id)] = {
        "officer_id": officer["id"],
        "incident_id": str(payload.incident_id),
        "status": status_value,
        "updated_at": officer["last_ping"],
    }

    manager = _context["manager"]
    await manager.broadcast({"type": "officer_update", "data": officer})
    await manager.broadcast(
        {
            "type": "dispatch_status_update",
            "data": {
                "officer_id": officer["id"],
                "incident_id": str(payload.incident_id),
                "status": status_value,
                "updated_at": officer["last_ping"],
            },
        }
    )

    return {
        "message": "Dispatch action recorded",
        "incident": incident,
        "officer": officer,
        "status": status_value,
    }
