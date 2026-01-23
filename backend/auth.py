from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt
import jwt
import hashlib
import uuid
from .config import JWT_SECRET, JWT_ALGORITHM, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, JWT_EXPIRATION_SECONDS
from .db import users
from .services.utils import get_malaysia_time

# Session Clearing Mechanism:
# By adding a unique salt on every startup, we invalidate all previously issued tokens.
STARTUP_SALT = str(uuid.uuid4())
DYNAMIC_JWT_SECRET = JWT_SECRET + STARTUP_SALT

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if not hashed_password:
            return False
            
        password_bytes = plain_password.encode('utf-8')
        
        # Handle cases where hashed_password might be bytes already (from some DB drivers)
        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode('utf-8')
        else:
            hashed_bytes = hashed_password
        
        # 1. Direct bcrypt check (no pre-hash)
        try:
            if bcrypt.checkpw(password_bytes, hashed_bytes):
                return True
        except Exception:
            pass
            
        # 2. SHA256 Hex Pre-hash (current IC strategy)
        try:
            pre_hex = hashlib.sha256(password_bytes).hexdigest().encode('utf-8')
            if bcrypt.checkpw(pre_hex, hashed_bytes):
                return True
        except Exception:
            pass
            
        # 3. SHA256 Binary Pre-hash (fallback)
        try:
            pre_bin = hashlib.sha256(password_bytes).digest()
            if bcrypt.checkpw(pre_bin, hashed_bytes):
                return True
        except Exception:
            pass

        # 4. Plain text comparison (LAST RESORT - only if hash doesn't look like bcrypt)
        # Bcrypt hashes always start with $2
        if not hashed_password.startswith('$2'):
            if plain_password == hashed_password:
                return True

        return False
    except Exception as e:
        print(f"DEBUG: verify_password error: {e}")
        return False

def hash_password(password: str) -> str:
    # Hash with SHA256 first to avoid bcrypt's 72-byte limit
    # and ensure consistent behavior across different environments
    pre_hashed = hashlib.sha256(password.encode('utf-8')).hexdigest().encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pre_hashed, salt).decode('utf-8')

def create_access_token(sub: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    now = get_malaysia_time()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(seconds=JWT_EXPIRATION_SECONDS)
    payload = {"sub": sub, "role": role, "exp": expire, "sid": STARTUP_SALT}
    return jwt.encode(payload, DYNAMIC_JWT_SECRET, algorithm=JWT_ALGORITHM)

from bson import ObjectId

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, DYNAMIC_JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id:
            print(f"DEBUG: Token decode success but no sub. Payload: {payload}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        
        # Try finding by ObjectId first (standard), then by str (fallback)
        try:
            # Ensure user_id is a string before converting to ObjectId or using in query
            safe_user_id = str(user_id)
            oid = ObjectId(safe_user_id)
            doc = await users.find_one({"_id": oid})
        except:
            doc = await users.find_one({"_id": safe_user_id})
            
        if not doc:
            # Fallback: try searching by string _id if ObjectId failed
            doc = await users.find_one({"_id": safe_user_id})
            
        if not doc:
            print(f"DEBUG: User not found in DB. ID: {user_id} (type: {type(user_id)})")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return {
            "id": str(doc["_id"]), 
            "email": doc["email"], 
            "role": role,
            "name": doc.get("name"),
            "target_job_title": doc.get("target_job_title", ""),
            "target_location": doc.get("target_location", ""),
            "has_analyzed": doc.get("has_analyzed", False)
        }
    except jwt.ExpiredSignatureError:
        print("DEBUG: Token expired")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception as e:
        print(f"DEBUG: Invalid token error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

async def ensure_admin():
    now = get_malaysia_time()
    # Ensure super admin
    existing_super = await users.find_one({"email": SUPERADMIN_EMAIL})
    if not existing_super:
        super_doc = {
            "email": SUPERADMIN_EMAIL,
            "password_hash": hash_password(SUPERADMIN_PASSWORD),
            "role": "super_admin",
            "created_at": now,
            "weekly_question_count": 0,
            "weekly_reset_at": now,
            "daily_resume_count": 0,
            "daily_interview_count": 0,
            "daily_reset_at": now,
        }
        await users.insert_one(super_doc)
    return True
