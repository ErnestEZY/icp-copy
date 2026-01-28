import os
import sys

# Add the parent directory to sys.path so we can import 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app

# This is for Vercel
# Vercel's Python runtime will look for the 'app' object in this file.
