# wsgi.py
from app.main import create_app

# This creates the app instance that Vercel will use
app = create_app()