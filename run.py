"""Entry point to launch the OSINT Intelligence Component server locally."""

import uvicorn
from app.config import settings
from app.logging_config import logger


def main():
    """Start the Uvicorn ASGI server."""
    logger.info(f"Starting {settings.app_name} on http://127.0.0.1:8000")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
