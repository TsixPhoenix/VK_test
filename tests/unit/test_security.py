"""Unit tests for security primitives."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.core.exceptions import InternalServiceError, UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_secret,
    encrypt_secret,
    verify_auth_credentials,
)
from cryptography.fernet import Fernet


def test_encrypt_decrypt_roundtrip(test_settings: Settings) -> None:
    """Encrypted credentials must be decrypted back to original value."""
    plaintext = "S3cure-P@ssword"
    encrypted = encrypt_secret(plaintext, settings=test_settings)

    assert encrypted != plaintext
    assert decrypt_secret(encrypted, settings=test_settings) == plaintext


def test_decode_invalid_token_raises_unauthorized(test_settings: Settings) -> None:
    """Invalid JWT should be rejected."""
    with pytest.raises(UnauthorizedError):
        decode_access_token("broken-token", settings=test_settings)


def test_create_and_decode_access_token(test_settings: Settings) -> None:
    """JWT creation should preserve subject and scopes."""
    token = create_access_token(
        subject="test-admin",
        scopes=["botfarm:read", "botfarm:write"],
        settings=test_settings,
    )
    payload = decode_access_token(token, settings=test_settings)

    assert payload["sub"] == "test-admin"
    assert payload["scopes"] == ["botfarm:read", "botfarm:write"]
    assert payload["exp"] is not None


def test_verify_auth_credentials(test_settings: Settings) -> None:
    """Configured credentials should pass, wrong values should fail."""
    assert verify_auth_credentials("botfarm_admin", "test-password", settings=test_settings)
    assert not verify_auth_credentials("wrong", "test-password", settings=test_settings)
    assert not verify_auth_credentials("botfarm_admin", "wrong", settings=test_settings)


def test_decrypt_invalid_ciphertext_raises_internal_error(test_settings: Settings) -> None:
    """Decrypt failures are internal server-side errors, not auth failures."""
    with pytest.raises(InternalServiceError):
        decrypt_secret("broken-ciphertext", settings=test_settings)


def test_encryption_key_rotation_with_fallback(test_settings: Settings) -> None:
    """Fallback keys should decrypt values encrypted by previous active key."""
    old_key = test_settings.botfarm_encryption_key
    new_key = Fernet.generate_key().decode("utf-8")
    old_settings = test_settings.model_copy(update={"botfarm_encryption_key": old_key})
    rotated_settings = test_settings.model_copy(
        update={
            "botfarm_encryption_key": new_key,
            "botfarm_encryption_fallback_keys": old_key,
        }
    )

    encrypted = encrypt_secret("legacy-password", settings=old_settings)
    assert decrypt_secret(encrypted, settings=rotated_settings) == "legacy-password"
