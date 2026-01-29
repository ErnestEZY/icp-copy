from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from backend.db import users
from backend.models import UserIn, Token
from backend.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.services.rate_limit import rate_limit
from backend.services.audit import log_event, check_admin_ip, trigger_admin_alert
from backend.services.utils import get_malaysia_time

from backend.config import (
    ADMIN_EMAILJS_PUBLIC_KEY, ADMIN_EMAILJS_SERVICE_ID, ADMIN_EMAILJS_TEMPLATE_ID,
    ADMIN_ALERT_EMAILJS_PUBLIC_KEY, ADMIN_ALERT_EMAILJS_SERVICE_ID, ADMIN_ALERT_EMAILJS_TEMPLATE_ID,
    GLOBAL_STARTUP_ID
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/test-auth")
async def test_auth():
    return {"message": "Auth router is working"}

@router.get("/config")
async def get_auth_config():
    """Exposes public configuration for EmailJS to the frontend"""
    return {
        "admin_emailjs_public_key": ADMIN_EMAILJS_PUBLIC_KEY,
        "admin_emailjs_service_id": ADMIN_EMAILJS_SERVICE_ID,
        "admin_emailjs_template_id": ADMIN_EMAILJS_TEMPLATE_ID,
        "admin_alert_emailjs_public_key": ADMIN_ALERT_EMAILJS_PUBLIC_KEY,
        "admin_alert_emailjs_service_id": ADMIN_ALERT_EMAILJS_SERVICE_ID,
        "admin_alert_emailjs_template_id": ADMIN_ALERT_EMAILJS_TEMPLATE_ID
    }

@router.post("/register", dependencies=[Depends(rate_limit)])
async def register(payload: UserIn, request: Request):
    # Ensure email is stripped and lowercase
    email = str(payload.email).strip().lower()
    ip_address = request.client.host if request.client else "unknown"
    
    # Check if user already exists in permanent collection
    existing = await users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    now = get_malaysia_time()
    
    # Directly create the permanent account (Skipping OTP)
    user_doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip() if payload.name else None,
        "role": "user",
        "created_at": now,
        "last_login_ip": ip_address,
        "is_verified": True, # Automatically verified
        "weekly_question_count": 0,
        "weekly_reset_at": now,
        "daily_resume_count": 0,
        "daily_interview_count": 0,
        "daily_reset_at": now,
    }
    
    await users.insert_one(user_doc)
    
    return {
        "message": "Registration successful! You can now login.",
        "email": email
    }

@router.get("/login")
async def login_get():
    return {"message": "Login endpoint exists, but you must use POST to login."}

@router.post("/login", response_model=Token)
@router.post("/login/", response_model=Token, include_in_schema=False)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Ensure username is stripped and lowercase
    username = str(form_data.username).strip().lower()
    ip_address = request.client.host if request.client else "unknown"
    
    # Lazy initialization for serverless
    try:
        from backend.auth import ensure_admin
        await ensure_admin()
    except Exception as e:
        print(f"DEBUG: Non-critical failure in lazy ensure_admin: {e}")
    
    try:
        # Try direct lookup first
        user = await users.find_one({"email": username})
        
        # Fallback: case-insensitive lookup (in case of legacy data)
        if not user:
            import re
            # We use a case-insensitive regex but ensure we match the whole string
            user = await users.find_one({"email": {"$regex": f"^{re.escape(username)}$", "$options": "i"}})
            if user:
                print(f"DEBUG: User found via case-insensitive fallback: {user.get('email')}")
            
        if not user:
            print(f"DEBUG: Login failed - User not found: {username}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
        
        # Debug the user object role
        db_email = user.get("email", "unknown")
        user_role = user.get("role", "user")
        print(f"DEBUG: Login attempt for '{username}'. Found in DB as '{db_email}' with role '{user_role}'")
        
        if not verify_password(form_data.password, user["password_hash"]):
            print(f"DEBUG: Login failed for {username}: Incorrect password")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
        
        # Update last login info
        await users.update_one({"_id": user["_id"]}, {"$set": {"last_login_ip": ip_address, "is_verified": True}})
        
        # Use the actual role from the database
        # This allows admins to login through the normal page as well, 
        # which fixes the user's reported issue.
        token = create_access_token(str(user["_id"]), user_role)
        return Token(access_token=token, startup_id=GLOBAL_STARTUP_ID)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"CRITICAL LOGIN ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Database connection error or internal failure: {str(e)}")

@router.post("/admin_login", response_model=Token, dependencies=[Depends(rate_limit)])
async def admin_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Ensure username is stripped and lowercase
    username = str(form_data.username).strip().lower()
    ip_address = request.client.host if request.client else "unknown"
    
    # Try direct lookup first
    user = await users.find_one({"email": username})
    
    # Fallback: case-insensitive lookup
    if not user:
        import re
        user = await users.find_one({"email": {"$regex": f"^{re.escape(username)}$", "$options": "i"}})
        
    if not user:
        await log_event(None, username, "admin_login", ip_address, "failure", {"reason": "user_not_found"})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    
    # IP Monitoring and Restrictions
    ip_status = await check_admin_ip(username, ip_address)
    
    if not verify_password(form_data.password, user["password_hash"]):
        print(f"DEBUG: Admin login failed for {username}: Incorrect password")
        await log_event(str(user["_id"]), username, "admin_login", ip_address, "failure", {"reason": "wrong_password"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    
    if user.get("role") not in ("admin", "super_admin"):
        await log_event(str(user["_id"]), username, "admin_login", ip_address, "failure", {"reason": "not_admin"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin or super_admin can login here")

    # Handle IP issues (Anomaly Detection)
    is_anomaly = False
    alert_reason = None
    
    # Check if IP is in allowlist
    if not ip_status["is_allowed"]:
        is_anomaly = True
        alert_reason = "Unknown IP access attempt (Not in Allowlist)"
        await log_event(str(user["_id"]), username, "admin_login", ip_address, "warning", {"reason": "unauthorized_ip"})
    
    # Check if IP changed since last login
    if ip_status["is_anomaly"]:
        is_anomaly = True
        # If we already have a reason (from allowlist), append this one
        anomaly_msg = f"IP Anomaly detected (Changed from: {ip_status['last_ip']})"
        alert_reason = f"{alert_reason} | {anomaly_msg}" if alert_reason else anomaly_msg
        await log_event(str(user["_id"]), username, "admin_login", ip_address, "warning", {"reason": "ip_anomaly"})

    # Trigger alert once if any anomaly was detected
    if is_anomaly:
        await trigger_admin_alert(username, ip_address, alert_reason)

    # Update last login info
    await users.update_one({"_id": user["_id"]}, {"$set": {"last_login_ip": ip_address}})
    
    await log_event(str(user["_id"]), username, "admin_login", ip_address, "success")
    
    # Ensure role is explicitly set to admin/super_admin for admin login
    role = user.get("role")
    if role not in ("admin", "super_admin"):
        role = "admin" # Fallback safety, though already checked above
        
    token = create_access_token(str(user["_id"]), role)
    
    # Fetch admin emails to return for frontend alerting as fallback
    admin_emails = []
    if is_anomaly:
        try:
            cursor = users.find({"role": {"$in": ["admin", "super_admin"]}})
            async for admin in cursor:
                if "email" in admin:
                    admin_emails.append(admin["email"])
        except Exception:
            pass

    return Token(
        access_token=token,
        is_anomaly=is_anomaly,
        admin_emails=admin_emails,
        alert_reason=alert_reason,
        startup_id=GLOBAL_STARTUP_ID
    )

@router.get("/me")
async def me(current=Depends(get_current_user)):
    return current
