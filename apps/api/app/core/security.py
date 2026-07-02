"""Security primitives.

This module contains only low-level security utilities:
  - Password hashing and verification (Argon2id)
  - Secure random session token generation
  - Cryptographic session token hashing

No HTTP, no FastAPI, no JWT.
Session management and authentication flows belong in modules/auth/.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# PasswordHasher defaults to Argon2id with recommended parameters
_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Return an Argon2id hash of ``plain``.

    Args:
        plain: The plaintext password to hash.

    Returns:
        An Argon2id hash string suitable for database storage.
    """
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify ``plain`` against a stored Argon2id ``hashed`` value.

    Args:
        plain: The plaintext password to verify.
        hashed: The stored Argon2id hash to compare against.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    """Generate a cryptographically secure random session token.

    Returns:
        A 32-byte (43-character URL-safe base64) opaque token string.
    """
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hash a session token using SHA-256 for secure database storage.

    Prevents token leakage in case of database read access.

    Args:
        token: The raw session token.

    Returns:
        A hex-encoded SHA-256 string.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
