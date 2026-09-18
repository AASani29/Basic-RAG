"""Logging setup, applied exactly once at startup.

There are no print() calls anywhere in this app. Everything goes through a
named logger so it carries a level, a timestamp and a source, and so the whole
app's verbosity is controlled by one env var.
"""

import logging
from logging.config import dictConfig

from app.core.config import Settings

# Key=value rather than prose. It stays readable in a terminal but is also
# greppable and splittable by a log shipper, which free-form messages are not.
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"


def configure_logging(settings: Settings) -> None:
    dictConfig(
        {
            "version": 1,
            # uvicorn installs its own handlers before our code runs. Without
            # this, its loggers survive and every request is logged twice.
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": _FORMAT, "datefmt": "%Y-%m-%d %H:%M:%S"}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    # stdout, not stderr: in Docker and most log collectors,
                    # stderr gets tagged as an error regardless of level.
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": settings.log_level},
            "loggers": {
                # Our own access log already records method/path/status, so
                # uvicorn's duplicate of it is silenced. Errors still surface
                # through uvicorn.error.
                "uvicorn.access": {"handlers": ["console"], "level": "WARNING", "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
                # SQL_ECHO=true routes generated SQL here at INFO.
                "sqlalchemy.engine": {"level": "INFO" if settings.sql_echo else "WARNING"},
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Namespaces every app logger under `app.*` so one line in configure_logging
    can change the level for our code without touching library loggers."""
    return logging.getLogger(f"app.{name}")
