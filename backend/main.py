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
    print(f"GLOBAL ERROR: {exc}")
    print(traceback.format_exc())
    
    # Don't expose detailed errors in production, but helpful for debugging now
    detail = str(exc)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "type": "HTTPException"}
        )
        
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal Server Error: {detail}",
            "type": type(exc).__name__,
            "traceback": traceback.format_exc() if os.getenv("DEBUG") == "true" else None
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(interview_router)
app.include_router(admin_router)
app.include_router(job_router)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Static global startup_id to persist across serverless function re-executions
# This prevents sessions from being cleared unnecessarily in environments like Vercel
_GLOBAL_STARTUP_ID = "1737273600" # Static ID for production stability

@app.on_event("startup")
async def startup():
    # Check DB Connection
    client = get_client()
    if client:
        try:
            await client.admin.command('ping')
            print("Successfully connected to MongoDB")
        except Exception as e:
            print(f"CRITICAL: Failed to connect to MongoDB: {e}")
    else:
        print("CRITICAL: MongoDB client not initialized")

    # Create TTL index for pending_users (expires after 15 minutes)
    if pending_users is not None:
        try:
            await pending_users.create_index("created_at", expireAfterSeconds=900)
        except Exception as e:
            print(f"Error creating TTL index for pending_users: {e}")

    # Initialize RAG Engine during startup
    rag_engine.initialize()
    
    # Ensure Admin and cleanup interviews
    from .auth import ensure_admin
    await ensure_admin()
    
    if interviews is not None:
        try:
            await interviews.update_many({"ended_at": None}, {"$set": {"ended_at": get_malaysia_time()}})
        except Exception:
            pass
    # Use the global static ID instead of a per-process timestamp
    app.state.startup_id = _GLOBAL_STARTUP_ID

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

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# Catch-all to serve index.html for any unknown routes (SPA support)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str):
    if not full_path:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    
    if full_path.startswith("api/"):
        return Response(status_code=404)
        
    try:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("index.html not found", status_code=404)
