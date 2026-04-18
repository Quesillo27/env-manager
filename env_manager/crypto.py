"""Encryption/decryption utilities using Fernet (AES-128-CBC + HMAC-SHA256)."""
import os
import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from .config import SALT_SIZE, PBKDF2_ITERATIONS as ITERATIONS


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from password + salt using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend(),
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt(data: str, password: str) -> bytes:
    """Encrypt a string. Returns: salt (16 bytes) + fernet_token."""
    salt = os.urandom(SALT_SIZE)
    key = derive_key(password, salt)
    f = Fernet(key)
    token = f.encrypt(data.encode())
    return salt + token


def decrypt(data: bytes, password: str) -> str:
    """Decrypt bytes produced by encrypt(). Raises ValueError on wrong password."""
    salt = data[:SALT_SIZE]
    token = data[SALT_SIZE:]
    key = derive_key(password, salt)
    f = Fernet(key)
    try:
        return f.decrypt(token).decode()
    except Exception as exc:
        raise ValueError("Decryption failed — wrong password or corrupted file") from exc
