"""Security primitives for auth, JWT, and credentials encryption."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import (
    AUTH_USERNAME,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    Settings,
    get_settings,
)
from app.core.exceptions import UnauthorizedError

AUTH_SCOPES: dict[str, str] = {
    "botfarm:read": "Read botfarm users and lock state.",
    "botfarm:write": "Create users and manage lock lifecycle.",
}


@lru_cache(maxsize=1)
def _build_fernet(key: str) -> Fernet:
    """Create and cache a Fernet cipher instance."""
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as exc:
        raise RuntimeError("Invalid BOTFARM_ENCRYPTION_KEY. Provide a valid Fernet key.") from exc


def encrypt_secret(plaintext: str, settings: Settings | None = None) -> str:
    """Encrypt plaintext value and return base64 ciphertext."""
    effective_settings = settings or get_settings()
    cipher = _build_fernet(effective_settings.botfarm_encryption_key)
    return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str, settings: Settings | None = None) -> str:
    """Decrypt ciphertext value and return plaintext."""
    effective_settings = settings or get_settings()
    cipher = _build_fernet(effective_settings.botfarm_encryption_key)
    try:
        return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise UnauthorizedError("Stored user credentials cannot be decrypted.") from exc


def create_access_token(
    subject: str,
    scopes: list[str],
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT for OAuth2 flows."""
    effective_settings = settings or get_settings()
    expire_delta = expires_delta or timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.now(UTC) + expire_delta
    payload = {"sub": subject, "scopes": scopes, "exp": expires_at}
    token = jwt.encode(
        payload,
        effective_settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )
    return str(token)


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    effective_settings = settings or get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            effective_settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise UnauthorizedError("Could not validate authentication token.") from exc
    return payload


def verify_auth_credentials(
    username: str,
    password: str,
    settings: Settings | None = None,
) -> bool:
    """Validate OAuth2 username/password pair against configured credentials."""
    effective_settings = settings or get_settings()
    is_username_valid = secrets.compare_digest(username, AUTH_USERNAME)
    is_password_valid = secrets.compare_digest(password, effective_settings.auth_password)
    return is_username_valid and is_password_valid
