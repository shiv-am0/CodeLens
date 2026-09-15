from typing import Optional

from pydantic import BaseModel, Field, SecretStr, field_validator


class AIConfigurationUpdate(BaseModel):
    admin_password: SecretStr
    api_key: Optional[SecretStr] = None
    chat_model: str = Field(min_length=1, max_length=255)
    encryption_key: Optional[SecretStr] = None

    @field_validator("chat_model")
    @classmethod
    def validate_chat_model(cls, value: str) -> str:
        model = value.strip()
        if not model:
            raise ValueError("Chat model is required")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._:")
        if any(character not in allowed for character in model):
            raise ValueError("Chat model contains unsupported characters")
        return model


class AIConfigurationResponse(BaseModel):
    provider: str
    configured: bool
    api_key_configured: bool
    chat_model: str
    embedding_model: str
    encryption_initialized: bool
    supported_chat_models: list[str]
