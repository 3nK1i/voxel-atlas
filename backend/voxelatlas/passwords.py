from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


_PASSWORD_HASHER = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    """Create an Argon2id hash for administrative credential provisioning."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must not be empty")
    return _PASSWORD_HASHER.hash(password)


def verify_password(stored_hash: str, candidate_password: str) -> bool:
    """Verify a candidate password against an Argon2id hash without leaking errors."""
    if not isinstance(stored_hash, str) or not stored_hash:
        return False
    if not isinstance(candidate_password, str):
        return False
    try:
        return bool(_PASSWORD_HASHER.verify(stored_hash, candidate_password))
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False
