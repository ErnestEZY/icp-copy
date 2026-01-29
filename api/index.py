import os
import sys

# Add the project root to sys.path so backend can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.main import create_app

# Create the FastAPI app instance
app = create_app()

# This is the entry point for Vercel
app = app
