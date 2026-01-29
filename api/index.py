import os
import sys

# Ensure the project root is in sys.path for absolute imports
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from backend.main import create_app
    # Create the real FastAPI application instance
    app = create_app()
except Exception as e:
    # Fallback to a minimal app if the main app fails to load,
    # but provide useful error information for debugging.
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI()
    
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    async def error_catch_all(full_path: str):
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "error": "Backend Load Failed",
                "detail": str(e),
                "type": type(e).__name__,
                "path": full_path,
                "traceback": traceback.format_exc()
            }
        )

