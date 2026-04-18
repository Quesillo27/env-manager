"""Structured logger with ENV_MANAGER_LOG_LEVEL control."""
import logging
import os

_level_name = os.environ.get("ENV_MANAGER_LOG_LEVEL", "WARNING").upper()
_level = getattr(logging, _level_name, logging.WARNING)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=_level,
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"env_manager.{name}")
