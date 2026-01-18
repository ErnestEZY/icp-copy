from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from .config import MONGO_URI, DB_NAME
import certifi
import sys

if not MONGO_URI or "your_mongodb_uri_here" in MONGO_URI:
    print("CRITICAL: MONGO_URI is not set or contains placeholder value!")
    # We don't exit here to allow the app to potentially start and show errors elsewhere
    # but most DB operations will fail.

try:
    client = AsyncIOMotorClient(
        MONGO_URI, 
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000, 
        connectTimeoutMS=10000
    )
    db = client[DB_NAME]
except Exception as e:
    print(f"ERROR: Failed to initialize MongoDB client: {e}")
    client = None
    db = None

# Proxy class to catch attempts to use the DB when it's not initialized
class DBErrorProxy:
    def __getattr__(self, name):
        # This catches .find_one, .insert_one, etc.
        def method(*args, **kwargs):
            raise RuntimeError(f"MongoDB not initialized (tried to call {name}). Check MONGO_URI environment variable in Vercel settings.")
        return method

    def __getitem__(self, name):
        # This catches db["users"]
        return self

if db is None:
    db_proxy = DBErrorProxy()
    users = db_proxy
    pending_users = db_proxy
    resumes = db_proxy
    interviews = db_proxy
    usage = db_proxy
    audit_logs = db_proxy
    fs = None
else:
    users = db["users"]
    pending_users = db["pending_users"]
    resumes = db["resumes"]
    interviews = db["interviews"]
    usage = db["usage"]
    audit_logs = db["audit_logs"]
    fs = AsyncIOMotorGridFSBucket(db, bucket_name="resume_files")
