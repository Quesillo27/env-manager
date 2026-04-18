"""Centralized configuration constants."""
import os
from pathlib import Path

PBKDF2_ITERATIONS = 390_000
SALT_SIZE = 16
VAULT_VERSION = 1

_custom = os.environ.get("ENV_MANAGER_VAULT")
if _custom:
    VAULT_FILE = Path(_custom)
    VAULT_DIR = VAULT_FILE.parent
else:
    VAULT_DIR = Path.home() / ".env-manager"
    VAULT_FILE = VAULT_DIR / "vault.enc"

ENV_VAR_KEY_PATTERN = r"^[A-Z_][A-Z0-9_]*$"
PROJECT_NAME_PATTERN = r"^[A-Za-z0-9_]([A-Za-z0-9_\-\.]*[A-Za-z0-9_])?$|^[A-Za-z0-9_]$"
