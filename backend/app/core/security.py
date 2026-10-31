from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32)

API_KEY_PREFIX = "kb_"
EMBED_TOKEN_PREFIX = "kbe_"

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 200


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def validate_password(password: str) -> str | None:
    """Return a human-readable problem or None when the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Das Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Das Passwort darf höchstens {MAX_PASSWORD_LENGTH} Zeichen lang sein."
    if password.strip() != password:
        return "Das Passwort darf nicht mit Leerzeichen beginnen oder enden."
    return None


def generate_token(prefix: str = "") -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def hash_token(token: str, pepper: str) -> str:
    return hashlib.sha256(f"{token}\0{pepper}".encode()).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return secrets.compare_digest(left, right)


def key_prefix(token: str) -> str:
    return token[:12]
