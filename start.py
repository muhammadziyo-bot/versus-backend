#!/usr/bin/env python3
"""
Digital Arena Backend Startup Script
"""

import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "start:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload to avoid platform issues
        log_level="info"
    )
