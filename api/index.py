import os
import sys

# Add the project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Also add backend dir directly for some serverless environments
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from backend.main import app
except Exception as e:
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI()
    
    @app.get("/api/index-debug")
    async def index_debug():
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "sys_path": sys.path,
            "root_dir": root_dir,
            "cwd": os.getcwd(),
            "files_in_root": os.listdir(root_dir) if os.path.exists(root_dir) else "not found",
            "files_in_backend": os.listdir(os.path.join(root_dir, "backend")) if os.path.exists(os.path.join(root_dir, "backend")) else "not found"
        }

# This is for Vercel
app = app
