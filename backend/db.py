from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from .config import MONGO_URI, DB_NAME
import certifi

client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
db = client[DB_NAME]

users = db["users"]
pending_users = db["pending_users"]
resumes = db["resumes"]
interviews = db["interviews"]
usage = db["usage"]
audit_logs = db["audit_logs"]
fs = AsyncIOMotorGridFSBucket(db, bucket_name="resume_files")
