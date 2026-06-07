"""
Authentication API — register, login, profile for 3 roles:
  blood_bank  → full admin access (Dashboard, Requests, Donors, Inventory, AI Insights)
  donor       → Donor Portal (profile, pending donation requests, respond)
  patient     → Patient Portal (own requests, create requests)
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt
import boto3
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("bloodbridge.auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

VALID_ROLES = {"blood_bank", "donor", "patient"}


# ── Pydantic models ──────────────────────────────────────────────────────────

class RegisterInput(BaseModel):
    email: str
    password: str
    name: str
    system_role: str           # blood_bank | donor | patient
    blood_group: Optional[str] = None
    phone_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str
    system_role: str
    blood_group: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class UserMeResponse(BaseModel):
    user_id: str
    email: str
    name: str
    system_role: str
    blood_group: Optional[str] = None
    phone_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: Optional[str] = None


# ── DynamoDB helpers ─────────────────────────────────────────────────────────

def _auth_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_AUTH_TABLE
    )


def _users_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_USERS_TABLE
    )


def _get_auth_user(email: str) -> Optional[dict]:
    resp = _auth_table().get_item(Key={"email": email})
    return resp.get("Item")


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _create_token(user_id: str, email: str, system_role: str, name: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "system_role": system_role,
        "name": name,
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def get_current_user(token: str = Depends(oauth2_scheme)) -> Optional[dict]:
    """Optional auth dependency — returns None if no token provided."""
    if not token:
        return None
    try:
        return decode_token(token)
    except HTTPException:
        return None


def require_auth(token: str = Depends(oauth2_scheme)) -> dict:
    """Strict auth dependency — raises 401 if no valid token."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(token)


def require_role(*roles: str):
    """Factory for role-restricted endpoints."""
    def dep(user: dict = Depends(require_auth)) -> dict:
        if user.get("system_role") not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
        return user
    return dep


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=LoginResponse, status_code=201)
def register(data: RegisterInput):
    if data.system_role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"system_role must be one of: {VALID_ROLES}")

    existing = _get_auth_user(data.email.lower())
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    password_hash = _hash_password(data.password)

    # Role mapping to bb_users role field
    role_map = {
        "blood_bank": "Volunteer",
        "donor": "Bridge Donor",
        "patient": "Patient",
    }

    # Store auth record
    _auth_table().put_item(Item={
        "email": data.email.lower(),
        "user_id": user_id,
        "password_hash": password_hash,
        "system_role": data.system_role,
        "name": data.name,
        "blood_group": data.blood_group or "Unknown",
        "phone_number": data.phone_number or "",
        "created_at": now,
    })

    # Create corresponding bb_users profile
    user_item = {
        "user_id": user_id,
        "email": data.email.lower(),
        "name": data.name,
        "role": role_map[data.system_role],
        "system_role": data.system_role,
        "blood_group": data.blood_group or "Unknown",
        "phone_number": data.phone_number or "",
        "consent_given": True,
        "consent_timestamp": now,
        "eligibility_status": "eligible",
        "user_donation_active_status": "Active",
        "status": "active",
        "registration_date": now[:10],
        "created_at": now,
    }
    if data.latitude is not None:
        user_item["latitude"] = str(data.latitude)
    if data.longitude is not None:
        user_item["longitude"] = str(data.longitude)

    _users_table().put_item(Item=user_item)

    token = _create_token(user_id, data.email.lower(), data.system_role, data.name)
    return LoginResponse(
        access_token=token,
        user_id=user_id,
        name=data.name,
        email=data.email.lower(),
        system_role=data.system_role,
        blood_group=data.blood_group,
        latitude=data.latitude,
        longitude=data.longitude,
    )


@router.post("/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    Login with email + password (OAuth2 form).
    Returns a JWT and the user's system_role for frontend routing.
    """
    auth_user = _get_auth_user(form.username.lower())
    if not auth_user or not _verify_password(form.password, auth_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(
        auth_user["user_id"],
        auth_user["email"],
        auth_user["system_role"],
        auth_user.get("name", ""),
    )

    # Look up bb_users for lat/lon
    profile = _users_table().get_item(Key={"user_id": auth_user["user_id"]}).get("Item", {})
    lat = float(profile["latitude"]) if profile.get("latitude") else None
    lon = float(profile["longitude"]) if profile.get("longitude") else None

    return LoginResponse(
        access_token=token,
        user_id=auth_user["user_id"],
        name=auth_user.get("name", ""),
        email=auth_user["email"],
        system_role=auth_user["system_role"],
        blood_group=auth_user.get("blood_group"),
        latitude=lat,
        longitude=lon,
    )


@router.get("/me", response_model=UserMeResponse)
def get_me(user: dict = Depends(require_auth)):
    """Return current user's profile from bb_users."""
    resp = _users_table().get_item(Key={"user_id": user["sub"]})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="User profile not found")

    return UserMeResponse(
        user_id=item["user_id"],
        email=item.get("email", user.get("email", "")),
        name=item.get("name", user.get("name", "")),
        system_role=item.get("system_role", user.get("system_role", "")),
        blood_group=item.get("blood_group"),
        phone_number=item.get("phone_number"),
        latitude=float(item["latitude"]) if item.get("latitude") else None,
        longitude=float(item["longitude"]) if item.get("longitude") else None,
        created_at=item.get("created_at"),
    )


@router.put("/me")
def update_me(updates: dict, user: dict = Depends(require_auth)):
    """Update current user's profile (name, phone_number, latitude, longitude)."""
    allowed = {"name", "phone_number", "latitude", "longitude", "blood_group"}
    clean = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not clean:
        raise HTTPException(status_code=400, detail="No valid update fields provided")

    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in clean)
    attr_names = {f"#{k}": k for k in clean}
    attr_values = {f":{k}": str(v) if k in ("latitude", "longitude") else v for k, v in clean.items()}
    attr_values[":now"] = datetime.utcnow().isoformat()
    expr += ", #upd = :now"
    attr_names["#upd"] = "updated_at"

    _users_table().update_item(
        Key={"user_id": user["sub"]},
        UpdateExpression=expr,
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )
    return {"updated": list(clean.keys())}
