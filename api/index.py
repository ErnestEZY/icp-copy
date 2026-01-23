import os
import sys

# Add the parent directory to sys.path so we can import 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.main import app
except Exception as e:
    import traceback
    print(f"CRITICAL: Failed to import app in index.py: {e}")
    print(traceback.format_exc())
    # Re-raise to let Vercel capture it, but now it's in the logs
    raise e

# This is for Vercel
# Vercel's Python runtime will look for the 'app' object in this file.
