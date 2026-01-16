import asyncio
import sys
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

# Add the project root to path so we can import backend as a package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.auth import hash_password
from backend.config import MONGO_URI, DB_NAME
from backend.services.utils import get_malaysia_time

async def create_admin_account():
    print("=== Manual Admin Registration Tool ===")
    
    # Initialize MongoDB client inside the async function to avoid loop conflicts
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    users_col = db["users"]
    
    email = input("Enter email: ").strip()
    if not email:
        print("Error: Email is required.")
        return

    password = input("Enter password: ").strip()
    if not password:
        print("Error: Password is required.")
        return

    role_choice = input("Select role (1: admin, 2: super_admin) [Default 1]: ").strip()
    role = "super_admin" if role_choice == "2" else "admin"

    # Check if user already exists
    try:
        existing = await users_col.find_one({"email": email})
        if existing:
            print(f"Error: User with email {email} already exists (Role: {existing.get('role')}).")
            confirm = input("Do you want to update this user's password and role? (y/n): ").lower()
            if confirm != 'y':
                return
            
            update_doc = {
                "$set": {
                    "password_hash": hash_password(password),
                    "role": role,
                    "updated_at": get_malaysia_time()
                }
            }
            await users_col.update_one({"email": email}, update_doc)
            print(f"Successfully updated {role} account for {email}")
        else:
            now = get_malaysia_time()
            admin_doc = {
                "email": email,
                "password_hash": hash_password(password),
                "role": role,
                "created_at": now,
                "weekly_question_count": 0,
                "weekly_reset_at": now,
                "daily_resume_count": 0,
                "daily_interview_count": 0,
                "daily_reset_at": now,
                "last_login_ip": None
            }
            await users_col.insert_one(admin_doc)
            print(f"Successfully created {role} account for {email}")
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(create_admin_account())
