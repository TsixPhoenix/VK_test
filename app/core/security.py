"""Security primitives for auth, JWT, and credentials encryption."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from jose import JWTError, jwt

from app.core.config import (
    AUTH_USERNAME,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    Settings,
    get_settings,
)
from app.core.exceptions import InternalServiceError, UnauthorizedError

AUTH_SCOPES: dict[str, str] = {
    "botfarm:read": "Read botfarm users and lock state.",
    "botfarm:write": "Create users and manage lock lifecycle.",
}


@lru_cache(maxsize=32)
def _build_fernet_chain(primary_key: str, fallback_keys: tuple[str, ...]) -> MultiFernet:
    """Create and cache Fernet chain for key rotation support."""
    all_keys = (primary_key, *fallback_keys)
    fernet_instances: list[Fernet] = []
    for key in all_keys:
        try:
            fernet_instances.append(Fernet(key.encode("utf-8")))
        except ValueError as exc:
            raise InternalServiceError(
                "Invalid encryption key configuration. Provide valid Fernet keys."
            ) from exc
    return MultiFernet(fernet_instances)


def encrypt_secret(plaintext: str, settings: Settings | None = None) -> str:
    """Encrypt plaintext value and return base64 ciphertext."""
    effective_settings = settings or get_settings()
    cipher = _build_fernet_chain(
        effective_settings.botfarm_encryption_key,
        tuple(effective_settings.encryption_fallback_keys),
    )
    return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str, settings: Settings | None = None) -> str:
    """Decrypt ciphertext value and return plaintext."""
    effective_settings = settings or get_settings()
    cipher = _build_fernet_chain(
        effective_settings.botfarm_encryption_key,
        tuple(effective_settings.encryption_fallback_keys),
    )
    try:
        return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise InternalServiceError(
            "Stored user credentials cannot be decrypted with configured encryption keys."
        ) from exc


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
