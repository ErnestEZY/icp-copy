import os
import sys

# Add the project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Handle the case where Vercel might be looking for 'app' in the current directory
try:
    from backend.main import app
except ImportError:
    # Try adding the root_dir to path again if it fails
    sys.path.append(root_dir)
    from backend.main import app

# This is the entry point for Vercel
app = app
