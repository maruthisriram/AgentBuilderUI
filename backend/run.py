"""
Entry point — run this file to start the backend server.
Usage: python run.py
"""

import uvicorn
from dotenv import load_dotenv

# Load env vars before anything else
load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
    )
