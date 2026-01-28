import os
import sys
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/health")
async def health():
    return {
        "status": "minimal_ok",
        "info": "This is a minimal diagnostic app. If you see this, the routing and Vercel setup are working.",
        "python_version": sys.version,
        "cwd": os.getcwd()
    }

@app.get("/api/debug-backend")
async def debug_backend():
    try:
        # Add the project root to sys.path
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        
        # Try importing main.py
        import backend.main as main_mod
        
        # Try calling create_app
        backend_app = main_mod.create_app()
        
        return {
            "status": "backend_load_success",
            "info": "Successfully loaded backend module and created app instance.",
            "sys_path": sys.path[:5]
        }
    except Exception as e:
        import traceback
        return {
            "status": "backend_load_failed",
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def catch_all(full_path: str):
    # Try to load and serve from backend if possible
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        from backend.main import app as backend_app
        # This is a bit tricky with FastAPI, we can't easily proxy like this
        # but for diagnostic purposes, we'll just return that it's available
        return {
            "status": "minimal_running",
            "path": full_path,
            "message": "The main backend is available but currently bypassed. Use /api/debug-backend to verify load."
        }
    except Exception:
        return {
            "status": "minimal_running",
            "path": full_path,
            "message": "The main backend failed to load. Use /api/debug-backend for details."
        }

# This is the entry point for Vercel
app = app

