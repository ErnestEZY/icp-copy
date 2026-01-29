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
        from backend.main import create_app
        backend_app = create_app()
        # In a real production environment, we'd use something like a proxy or 
        # direct integration, but for diagnosis we'll check if the route exists
        return {
            "status": "minimal_running",
            "path": full_path,
            "message": "The main backend is available. Use /api/debug-backend for details."
        }
    except Exception:
        return {
            "status": "minimal_running",
            "path": full_path,
            "message": "The main backend failed to load."
        }

# This is the entry point for Vercel
app = app
