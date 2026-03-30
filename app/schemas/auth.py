"""Schemas for authentication flows."""

from pydantic import BaseModel, ConfigDict, Field


class TokenPayload(BaseModel):
    """Decoded JWT payload used by authorization dependencies."""

    sub: str
    scopes: list[str] = Field(default_factory=list)
    exp: int


class TokenResponse(BaseModel):
    """OAuth2 access token response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "<jwt>",
                "token_type": "bearer",
                "expires_in": 1800,
                "scope": "botfarm:read botfarm:write",
            }
        }
    )

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scope: str
