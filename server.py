from core.logging_config import configure_logging


configure_logging()

from app.main import app


__all__ = ["app"]
