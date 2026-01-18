from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from .config import MONGO_URI, DB_NAME
import certifi
import asyncio

class DatabaseManager:
    _client = None
    _db = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            if not MONGO_URI or "your_mongodb_uri_here" in MONGO_URI:
                print("CRITICAL: MONGO_URI is not set!")
                return None
            
            try:
                # Motor will use the current running loop if we don't pass one
                cls._client = AsyncIOMotorClient(
                    MONGO_URI,
                    tlsCAFile=certifi.where(),
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    # Crucial for serverless: don't pre-bind to a loop
                    io_loop=asyncio.get_event_loop() 
                )
            except Exception as e:
                print(f"ERROR: Failed to initialize MongoDB client: {e}")
                return None
        return cls._client

    @classmethod
    def get_db(cls):
        if cls._db is None:
            client = cls.get_client()
            if client is not None:
                cls._db = client[DB_NAME]
        return cls._db

# Proxy objects that delegate to the actual collection on every access
# This ensures we always use the current loop's client
class CollectionProxy:
    def __init__(self, collection_name):
        self._name = collection_name

    def _get_col(self):
        db = DatabaseManager.get_db()
        if db is None:
            raise RuntimeError(f"MongoDB not initialized. Tried to access {self._name}")
        return db[self._name]

    def __getattr__(self, name):
        return getattr(self._get_col(), name)

# These will be imported by other files
users = CollectionProxy("users")
pending_users = CollectionProxy("pending_users")
resumes = CollectionProxy("resumes")
interviews = CollectionProxy("interviews")
usage = CollectionProxy("usage")
audit_logs = CollectionProxy("audit_logs")

# For GridFS, we need a slightly different approach
class GridFSProxy:
    _fs = None
    
    @classmethod
    def get_fs(cls):
        if cls._fs is None:
            db = DatabaseManager.get_db()
            if db is not None:
                cls._fs = AsyncIOMotorGridFSBucket(db, bucket_name="resume_files")
        return cls._fs

    def __getattr__(self, name):
        fs = self.get_fs()
        if fs is None:
            raise RuntimeError("GridFS not initialized")
        return getattr(fs, name)

fs = GridFSProxy()

# Export client for startup ping
def get_client():
    return DatabaseManager.get_client()
