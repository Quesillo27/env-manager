"""Input validation helpers."""
import re
from .config import ENV_VAR_KEY_PATTERN, PROJECT_NAME_PATTERN


class ValidationError(ValueError):
    pass


def validate_key(key: str) -> None:
    """Raise ValidationError if key is not a valid env var name."""
    if not key:
        raise ValidationError("Key name cannot be empty")
    if not re.match(ENV_VAR_KEY_PATTERN, key):
        raise ValidationError(
            f"Invalid key '{key}': must match [A-Z_][A-Z0-9_]* "
            "(uppercase letters, digits, underscores only)"
        )


def validate_project(name: str) -> None:
    """Raise ValidationError if project name is invalid."""
    if not name:
        raise ValidationError("Project name cannot be empty")
    if len(name) > 64:
        raise ValidationError("Project name must be 64 characters or fewer")
    if not re.match(PROJECT_NAME_PATTERN, name):
        raise ValidationError(
            f"Invalid project name '{name}': use letters, digits, underscores, hyphens, dots"
        )
