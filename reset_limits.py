import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Add the project root to sys.path so we can import from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def reset_limits(email: str = None):
    # Load environment variables
    load_dotenv()
    
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "interview_coach_prep")
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    users = db["users"]
    
    if email:
        # Reset specific user
        result = await users.update_one(
            {"email": email},
            {"$set": {
                "daily_resume_count": 0,
                "daily_interview_count": 0,
                "daily_reset_at": None # This will trigger a fresh reset check
            }}
        )
        if result.modified_count > 0:
            print(f"Successfully reset limits for {email}")
        else:
            print(f"No user found with email {email}")
    else:
        # Reset all users
        result = await users.update_many(
            {},
            {"$set": {
                "daily_resume_count": 0,
                "daily_interview_count": 0,
                "daily_reset_at": None
            }}
        )
        print(f"Successfully reset limits for {result.modified_count} users")

if __name__ == "__main__":
    target_email = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(reset_limits(target_email))
