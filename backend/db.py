from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from backend.config import MONGO_URI, DB_NAME
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
            # Fallback if no loop is running (e.g., during initialization in some environments)
            current_loop = None

        # Re-initialize if client is missing or loop has changed (critical for serverless)
        if cls._client is None or (current_loop is not None and cls._loop != current_loop):
            if not MONGO_URI or "your_mongodb_uri_here" in MONGO_URI:
                print("CRITICAL: MONGO_URI is not set or using placeholder!")
                return None
            
            try:
                # Optimized for Serverless: smaller pools, specific timeouts
                cls._client = AsyncIOMotorClient(
                    MONGO_URI,
                    tlsCAFile=certifi.where(),
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=20000,
                    maxPoolSize=1, # Reduced for serverless concurrency
                    minPoolSize=1,
                    retryWrites=True,
                    retryReads=True
                )
                cls._loop = current_loop
                print(f"INFO: MongoDB client re-initialized (loop: {id(current_loop)})")
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
# Note: These proxies are safe to use globally as they resolve the database 
# dynamically on every access, ensuring compatibility with serverless event loops.
users = CollectionProxy("users")
resumes = CollectionProxy("resumes")
interviews = CollectionProxy("interviews")
usage = CollectionProxy("usage")
audit_logs = CollectionProxy("audit_logs")

# For GridFS, we need a slightly different approach
class GridFSProxy:
    _fs = None
    _loop = None
    
    @classmethod
    async def get_fs(cls):
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if cls._fs is None or (current_loop is not None and cls._loop != current_loop):
            db = DatabaseManager.get_db()
            if db is not None:
                cls._fs = AsyncIOMotorGridFSBucket(db, bucket_name="resume_files")
                cls._loop = current_loop
        return cls._fs

    def __getattr__(self, name):
        # Note: This sync __getattr__ might fail if it tries to call an async method 
        # without await, but for the proxy usage it usually just returns the method.
        # However, for GridFS it's better to use get_fs() directly since it's async-init.
        raise RuntimeError("Use 'await fs.get_fs()' instead of direct access for GridFSProxy")

fs = GridFSProxy()

# Export client for startup ping
def get_client():
    return DatabaseManager.get_client()
