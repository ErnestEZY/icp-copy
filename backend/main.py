import os
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Use absolute-style imports for Vercel compatibility
from routes.auth_routes import router as auth_router
from routes.resume_routes import router as resume_router
from routes.interview_routes import router as interview_router
from routes.admin_routes import router as admin_router
from routes.job_routes import router as job_router
from services.rag_engine import rag_engine
from services.utils import get_malaysia_time
from db import interviews, pending_users

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # We use Bearer tokens in headers, so credentials (cookies) are not required for CORS
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(interview_router)
app.include_router(admin_router)
app.include_router(job_router)

@app.get("/api/meta/startup_id")
async def startup_id():
    return {"startup_id": getattr(app.state, "startup_id", "")}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)
