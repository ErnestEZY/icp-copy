import os
import time
import traceback
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import HTMLResponse

# Use absolute paths for directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

print(f"INFO: Initializing FastAPI application... (BASE_DIR: {BASE_DIR})")

# Helper to simplify operation IDs for cleaner API docs
def simplify_operation_ids(app: FastAPI) -> None:
    from fastapi.routing import APIRoute
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name

# Import routes inside a function to avoid circular/early import issues
def include_routes(app: FastAPI):
    try:
        from backend.routes import auth_routes, resume_routes, interview_routes, admin_routes
        app.include_router(auth_routes.router, prefix="/api")
        app.include_router(resume_routes.router, prefix="/api")
        app.include_router(interview_routes.router, prefix="/api")
        app.include_router(admin_routes.router, prefix="/api")
        print("INFO: All routes included successfully with /api prefix.")
    except Exception as e:
        print(f"ERROR: Failed to include routes: {e}")
        import traceback
        traceback.print_exc()

# Static global startup_id to persist across serverless function re-executions
from backend.config import GLOBAL_STARTUP_ID
_GLOBAL_STARTUP_ID = GLOBAL_STARTUP_ID

def create_app():
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles

    limiter = Limiter(key_func=get_remote_address)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Global error handler for debugging
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        method = request.method
        url = str(request.url)
        print(f"GLOBAL ERROR: {method} {url} - {exc}")
        import traceback
        print(traceback.format_exc())
        
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

    include_routes(app)
    simplify_operation_ids(app)

    # Use absolute path for static files
    static_dir = os.path.join(FRONTEND_DIR, "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        print(f"INFO: Static files mounted from {static_dir}")
    else:
        print(f"WARNING: Static directory not found at {static_dir}")

    @app.get("/api/meta/startup_id")
    async def startup_id():
        return {"startup_id": _GLOBAL_STARTUP_ID}

    @app.get("/api/health")
    async def health():
        db_status = "not_checked"
        try:
            from backend.db import get_client
            client = get_client()
            if client:
                await client.admin.command('ping')
                db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        return {
            "status": "ok",
            "database": db_status
        }

    @app.post("/api/test-post")
    async def test_post(data: dict = None):
        return {"message": "POST successful", "received": data}

    @app.get("/api/debug-routes")
    async def debug_routes():
        routes = []
        for route in app.routes:
            routes.append({
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if hasattr(route, "methods") else None
            })
        return {"routes": routes}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        from fastapi.responses import FileResponse, Response
        favicon_path = os.path.join(FRONTEND_DIR, "static", "favicon-32x32.png")
        if os.path.exists(favicon_path):
            return FileResponse(favicon_path)
        return Response(status_code=204)

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    async def catch_all(request: Request, full_path: str):
        method = request.method
        url = str(request.url)
        path = request.url.path
        print(f"DEBUG: Final Catch-all reached: {method} {url} (full_path: {full_path}, path: {path})")
        
        # If it's a GET request and doesn't look like an API call, serve the frontend
        if method == "GET" and not path.startswith("/api/"):
            from fastapi.responses import HTMLResponse
            index_path = os.path.join(FRONTEND_DIR, "index.html")
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            except FileNotFoundError:
                return HTMLResponse(f"index.html not found at {index_path}", status_code=404)
        
        # If it's an API call that reached here, it's a 404
        if path.startswith("/api/"):
            # Log all available routes for debugging when a 404 occurs on an API route
            available_routes = []
            for r in app.routes:
                methods = list(r.methods) if hasattr(r, 'methods') else []
                path_str = r.path if hasattr(r, 'path') else str(r)
                available_routes.append(f"{methods} {path_str}")
            
            print(f"DEBUG: 404 on API route. Available routes: {available_routes}")
            
            return JSONResponse(
                status_code=404,
                content={
                    "detail": f"API route not found: {method} {path}",
                    "path": path,
                    "full_path_param": full_path,
                    "method": method,
                    "available_routes_count": len(available_routes),
                    "tip": "Check if the route is registered in include_routes() and has the correct prefix."
                }
            )
        
        # Default fallback for other methods/paths
        return JSONResponse(
            status_code=405 if method != "GET" else 404,
            content={
                "detail": "Method Not Allowed" if method != "GET" else "Not Found",
                "method": method,
                "path": path,
                "info": "Reached catch-all in main.py"
            }
        )

    return app

app = create_app()
