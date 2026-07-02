"""Security primitives.

This module contains only low-level security utilities:
  - Password hashing and verification (bcrypt via passlib)

No HTTP, no FastAPI, no JWT.
Session management and authentication flows belong in modules/auth/.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of ``plain``.

    Args:
        plain: The plaintext password to hash.

    Returns:
        A bcrypt hash string suitable for database storage.
    """
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify ``plain`` against a stored bcrypt ``hashed`` value.

    Args:
        plain: The plaintext password to verify.
        hashed: The stored bcrypt hash to compare against.

    Returns:
        True if the password matches, False otherwise.
    """
    return _pwd_context.verify(plain, hashed)
