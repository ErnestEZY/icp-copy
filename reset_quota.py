import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.utils import get_malaysia_time

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "interview_coach")

async def reset_user_quota(email):
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    users = db.users
    
    user = await users.find_one({"email": email})
    if not user:
        print(f"Error: User with email '{email}' not found.")
        return

    from datetime import datetime, timezone
    now = get_malaysia_time()
    
    await users.update_one(
        {"email": email},
        {
            "$set": {
                "daily_question_count": 0,
                "daily_resume_count": 0,
                "daily_interview_count": 0,
                "daily_reset_at": now,
                # Compatibility for old records
                "weekly_question_count": 0,
                "weekly_reset_at": now
            }
        }
    )
    print(f"Success: Quotas reset for {email}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reset_quota.py <user_email>")
        sys.exit(1)
    
    email = sys.argv[1]
    asyncio.run(reset_user_quota(email))
