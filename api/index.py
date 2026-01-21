"""Vercel serverless handler for FastAPI app."""
from api.main import app

# Vercel requires a handler named 'handler'
handler = app
