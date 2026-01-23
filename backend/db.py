from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from .config import MONGO_URI, DB_NAME
import certifi
import asyncio

class DatabaseManager:
    _client = None
    _db = None
    _loop = None

    @classmethod
    def get_client(cls):
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # Re-initialize if client is missing or loop has changed
        if cls._client is None or (current_loop is not None and cls._loop != current_loop):
            if not MONGO_URI or "your_mongodb_uri_here" in MONGO_URI:
                print("CRITICAL: MONGO_URI is not set or using placeholder!")
                return None
            
            try:
                cls._client = AsyncIOMotorClient(
                    MONGO_URI,
                    tlsCAFile=certifi.where(),
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=20000,
                    maxPoolSize=10,
                    minPoolSize=1,
                    retryWrites=True,
                    retryReads=True
                )
                cls._loop = current_loop
                print(f"INFO: MongoDB client initialized (loop: {id(current_loop)})")
            except Exception as e:
                print(f"ERROR: Failed to initialize MongoDB client: {e}")
                cls._client = None
                cls._loop = None
                return None
        return cls._client

    @classmethod
    def get_db(cls):
        client = cls.get_client()
        if client is not None:
            return client[DB_NAME]
        return None

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
