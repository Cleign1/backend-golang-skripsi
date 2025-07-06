#!/usr/bin/env python3
"""
Main entry point for the AI Agents Stock Management System.

This script starts the FastAPI server with the AI agents orchestrator.
"""

import asyncio
import uvicorn
from agents.api.main import app
from agents.config.settings import settings
from agents.utils.logging import setup_logging

def main():
    """Main entry point."""
    # Setup logging
    setup_logging(level="INFO")
    
    # Start the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.server.port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()