from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from app.core.config import settings
from app.services.ai_configuration import AIConfigurationService
from app.services.key_manager import key_manager
from app.services.master_key_store import master_key_store


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "admin_password", "test-admin-password")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "encryption_key", "")
    monkeypatch.setattr(master_key_store, "path", tmp_path / "master.key")
    monkeypatch.setattr(master_key_store, "_fernet", None)
    monkeypatch.setattr(master_key_store, "_key", None)
    key_manager._fallback_key = ""
    key_manager.invalidate()


@pytest.mark.asyncio
async def test_status_reports_missing_configuration(client: AsyncClient):
    response = await client.get("/api/settings/ai")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["api_key_configured"] is False
    assert "api_key" not in response.json()


@pytest.mark.asyncio
async def test_ollama_environment_configuration_remains_ready(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "llm_provider", "ollama")

    response = await client.get("/api/settings/ai")

    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"
    assert response.json()["configured"] is True


@pytest.mark.asyncio
async def test_analyze_is_rejected_before_work_when_configuration_is_missing(
    client: AsyncClient,
):
    response = await client.post(
        "/api/repositories/analyze",
        json={"github_url": "https://github.com/example/project"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AI_CONFIGURATION_REQUIRED"


@pytest.mark.asyncio
async def test_configuration_rejects_incorrect_admin_password(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(
        AIConfigurationService,
        "_validate_openai",
        AsyncMock(return_value=None),
    )

    response = await client.put(
        "/api/settings/ai",
        json={
            "admin_password": "wrong-password",
            "api_key": "secret-api-key",
            "chat_model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "ADMIN_AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_configuration_generates_key_and_never_returns_secrets(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(
        AIConfigurationService,
        "_validate_openai",
        AsyncMock(return_value=None),
    )

    response = await client.put(
        "/api/settings/ai",
        json={
            "admin_password": "test-admin-password",
            "api_key": "secret-api-key",
            "chat_model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["api_key_configured"] is True
    assert payload["encryption_initialized"] is True
    assert "secret-api-key" not in response.text
    assert "test-admin-password" not in response.text
    assert master_key_store.path.exists()
    assert master_key_store.path.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_configuration_accepts_custom_initial_encryption_key(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(
        AIConfigurationService,
        "_validate_openai",
        AsyncMock(return_value=None),
    )
    custom_key = Fernet.generate_key().decode()

    response = await client.put(
        "/api/settings/ai",
        json={
            "admin_password": "test-admin-password",
            "api_key": "secret-api-key",
            "chat_model": "gpt-4o",
            "encryption_key": custom_key,
        },
    )

    assert response.status_code == 200
    assert master_key_store.path.read_text() == custom_key


@pytest.mark.asyncio
async def test_invalid_custom_encryption_key_is_rejected_before_openai_validation(
    client: AsyncClient, monkeypatch
):
    validate_openai = AsyncMock(return_value=None)
    monkeypatch.setattr(AIConfigurationService, "_validate_openai", validate_openai)

    response = await client.put(
        "/api/settings/ai",
        json={
            "admin_password": "test-admin-password",
            "api_key": "secret-api-key",
            "chat_model": "gpt-4o-mini",
            "encryption_key": "not-a-fernet-key",
        },
    )

    assert response.status_code == 422
    validate_openai.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_update_preserves_the_existing_api_key(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(
        AIConfigurationService,
        "_validate_openai",
        AsyncMock(return_value=None),
    )
    initial_response = await client.put(
        "/api/settings/ai",
        json={
            "admin_password": "test-admin-password",
            "api_key": "secret-api-key",
            "chat_model": "gpt-4o-mini",
        },
    )
    assert initial_response.status_code == 200

    update_response = await client.put(
        "/api/settings/ai",
        json={
            "admin_password": "test-admin-password",
            "chat_model": "gpt-4o",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["chat_model"] == "gpt-4o"
    assert update_response.json()["api_key_configured"] is True


@pytest.mark.asyncio
async def test_failed_openai_validation_does_not_create_a_master_key(
    client: AsyncClient, monkeypatch
):
    from app.services.ai_configuration import AIConfigurationValidationError

    monkeypatch.setattr(
        AIConfigurationService,
        "_validate_openai",
        AsyncMock(side_effect=AIConfigurationValidationError("Validation failed")),
    )

    response = await client.put(
        "/api/settings/ai",
        json={
            "admin_password": "test-admin-password",
            "api_key": "bad-api-key",
            "chat_model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 422
    assert not master_key_store.path.exists()
