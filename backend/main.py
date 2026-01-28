from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import HTMLResponse
from .routes.auth_routes import router as auth_router
from .routes.resume_routes import router as resume_router
from .routes.interview_routes import router as interview_router
from .routes.admin_routes import router as admin_router
from .routes.job_routes import router as job_router
from .services.rag_engine import rag_engine
from .services.utils import get_malaysia_time
from .db import interviews, pending_users, get_client
import os

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global error handler for debugging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    method = request.method
    url = str(request.url)
    print(f"GLOBAL ERROR: {method} {url} - {exc}")
    print(traceback.format_exc())
    
    # Don't expose detailed errors in production, but helpful for debugging now
    detail = str(exc)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail, 
                "type": "HTTPException",
                "method": method,
                "url": url
            }
        )
        
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal Server Error: {detail}",
            "type": type(exc).__name__,
            "method": method,
            "url": url,
            "traceback": traceback.format_exc() if os.getenv("DEBUG") == "true" else None
        }
    )

@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=405,
        content={
            "detail": "Method Not Allowed (FastAPI Handler)",
            "method": request.method,
            "url": str(request.url),
            "suggestion": "Check if the endpoint exists and accepts this method."
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start_time = time.time()
    method = request.method
    path = request.url.path
    print(f"DEBUG: Incoming Request: {method} {path}")
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        print(f"DEBUG: Response: {response.status_code} for {method} {path} (took {process_time:.2f}ms)")
        return response
    except Exception as e:
        import traceback
        print(f"DEBUG: Request Failed: {method} {path} - Error: {e}")
        print(traceback.format_exc())
        raise e

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(interview_router)
app.include_router(admin_router)
app.include_router(job_router)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Static global startup_id to persist across serverless function re-executions
# This prevents sessions from being cleared unnecessarily in environments like Vercel
_GLOBAL_STARTUP_ID = "1737273600" # Static ID for production stability

# Flag to prevent duplicate initializations in serverless
_INITIALIZED = False

# Use absolute path for frontend/index.html
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

@app.on_event("startup")
async def startup():
    global _INITIALIZED
    if _INITIALIZED:
        return
    
    print("INFO: Initializing application startup...")
    
    # Check DB Connection
    client = get_client()
    if client:
        try:
            import asyncio
            print("DEBUG: Pinging MongoDB...")
            await asyncio.wait_for(client.admin.command('ping'), timeout=5.0)
            print("Successfully connected to MongoDB")
        except Exception as e:
            print(f"CRITICAL: Failed to connect to MongoDB: {e}")
    else:
        print("CRITICAL: MongoDB client not initialized")

    # Create TTL index for pending_users (expires after 15 minutes)
    try:
        from .db import DatabaseManager
        db = DatabaseManager.get_db()
        if db is not None:
            print("DEBUG: Checking TTL indexes...")
            indexes = await db["pending_users"].index_information()
            if "created_at_1" not in indexes:
                await db["pending_users"].create_index("created_at", expireAfterSeconds=900)
                print("INFO: TTL index created for pending_users")
            else:
                print("INFO: TTL index already exists for pending_users")
    except Exception as e:
        print(f"Error creating TTL index for pending_users: {e}")

    # Initialize RAG Engine during startup
    try:
        print("DEBUG: Initializing RAG Engine...")
        rag_engine.initialize()
    except Exception as e:
        print(f"Error initializing RAG Engine: {e}")
    
    # Ensure Admin and cleanup interviews
    try:
        print("DEBUG: Ensuring admin user...")
        from .auth import ensure_admin
        await ensure_admin()
    except Exception as e:
        print(f"Error ensuring admin: {e}")
    
    if interviews is not None:
        try:
            print("DEBUG: Cleaning up active interviews...")
            await interviews.update_many({"ended_at": None}, {"$set": {"ended_at": get_malaysia_time()}})
        except Exception:
            pass
            
    app.state.startup_id = _GLOBAL_STARTUP_ID
    _INITIALIZED = True
    print("INFO: Application startup complete.")

@app.get("/api/meta/startup_id")
async def startup_id():
    return {"startup_id": getattr(app.state, "startup_id", _GLOBAL_STARTUP_ID)}

@app.get("/api/meta/startup_id")
async def startup_id():
    return {"startup_id": getattr(app.state, "startup_id", _GLOBAL_STARTUP_ID)}

@app.get("/api/health")
async def health_check():
    health = {
        "status": "ok", 
        "database": "unknown",
        "env_check": {
            "MONGO_URI_SET": bool(os.getenv("MONGO_URI")),
            "DB_NAME": os.getenv("DB_NAME", "interview_coach"),
            "JWT_SECRET_SET": bool(os.getenv("JWT_SECRET"))
        }
    }
    client = get_client()
    if client:
        try:
            import asyncio
            # Short timeout for health check
            await asyncio.wait_for(client.admin.command('ping'), timeout=2.0)
            health["database"] = "connected"
        except asyncio.TimeoutError:
            health["database"] = "timeout"
        except Exception as e:
            health["database"] = f"error: {str(e)}"
    else:
        health["database"] = "not_initialized (check MONGO_URI)"
    return health

@app.get("/api/debug-routes")
async def debug_routes():
    routes = []
    for route in app.routes:
        methods = list(route.methods) if hasattr(route, "methods") else []
        routes.append({
            "path": route.path,
            "name": getattr(route, "name", "unnamed"),
            "methods": methods
        })
    return {"routes": routes}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# Catch-all to serve index.html for any unknown routes (SPA support)
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def catch_all(request: Request, full_path: str):
    method = request.method
    url = str(request.url)
    print(f"DEBUG: Final Catch-all reached: {method} {url} (full_path: {full_path})")
    
    # If it's a GET request and not for /api, it might be for the SPA
    if method == "GET" and not full_path.startswith("api/"):
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return HTMLResponse(f"index.html not found at {index_path}", status_code=404)
    
    # If it's an API request that got here, it means it didn't match any route
    if full_path.startswith("api/"):
        return JSONResponse(
            status_code=404,
            content={
                "detail": f"API route not found: {method} {url}",
                "path": full_path,
                "method": method
            }
        )
    
    # Default fallback for other methods/paths
    return Response(status_code=405 if method != "GET" else 404)
