"""
Application Entry Point
Run the GitHub Cloud Connector server.
"""

import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    env = os.getenv("APP_ENV", "development")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=(env == "development"),
        log_level="info",
    )
