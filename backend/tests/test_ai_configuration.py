import re
from unittest.mock import AsyncMock

import bcrypt
import pytest
from httpx import AsyncClient

from app.core.config import settings, validate_security_settings
from app.core.rate_limit import admin_login_limiter
from app.services.admin_auth import admin_auth
from app.services.ai_configuration import AIConfigurationService
from app.services.key_manager import key_manager
from app.services.master_key_store import master_key_store


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "admin_password", "test-admin-password")
    monkeypatch.setattr(settings, "admin_password_hash", "")
    monkeypatch.setattr(settings, "admin_session_secret", "test-session-secret-that-is-long-enough")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "encryption_key", "")
    monkeypatch.setattr(master_key_store, "path", tmp_path / "master.key")
    monkeypatch.setattr(master_key_store, "_fernet", None)
    monkeypatch.setattr(master_key_store, "_key", None)
    key_manager._fallback_key = ""
    key_manager.invalidate()
    admin_login_limiter._requests.clear()


@pytest.mark.asyncio
async def test_status_reports_missing_configuration(client: AsyncClient):
    response = await client.get("/api/settings/ai")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["api_key_configured"] is False
    assert "api_key" not in response.json()


@pytest.mark.asyncio
async def test_public_configuration_writes_are_disabled(client: AsyncClient):
    response = await client.put(
        "/api/settings/ai",
        json={"api_key": "public-secret", "chat_model": "gpt-4o-mini"},
    )

    assert response.status_code == 405


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
async def test_owner_kill_switch_disables_ai_features(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "environment-key")
    monkeypatch.setattr(settings, "ai_features_enabled", False)

    response = await client.get("/api/settings/ai")

    assert response.status_code == 200
    assert response.json()["api_key_configured"] is True
    assert response.json()["configured"] is False


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
async def test_admin_settings_require_a_valid_signed_session(client: AsyncClient):
    response = await client.get("/admin/settings", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


@pytest.mark.asyncio
async def test_admin_login_rejects_incorrect_password(client: AsyncClient):
    response = await client.post(
        "/admin/login", data={"password": "wrong-password"}, follow_redirects=False
    )

    assert response.status_code == 401
    assert "codelens_admin_session" not in response.cookies


def test_admin_password_hash_is_supported(monkeypatch):
    password_hash = bcrypt.hashpw(b"owner-password", bcrypt.gensalt()).decode()
    monkeypatch.setattr(settings, "admin_password", "")
    monkeypatch.setattr(settings, "admin_password_hash", password_hash)

    assert admin_auth.verify_password("owner-password") is True
    assert admin_auth.verify_password("wrong-password") is False


async def _login_and_get_csrf(client: AsyncClient) -> str:
    login_response = await client.post(
        "/admin/login",
        data={"password": "test-admin-password"},
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    page = await client.get("/admin/settings")
    assert page.status_code == 200
    match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert match is not None
    return match.group(1)


@pytest.mark.asyncio
async def test_admin_can_configure_shared_key_and_model(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(
        AIConfigurationService,
        "_validate_openai",
        AsyncMock(return_value=None),
    )
    csrf_token = await _login_and_get_csrf(client)

    response = await client.post(
        "/admin/settings",
        data={
            "csrf_token": csrf_token,
            "api_key": "secret-api-key",
            "chat_model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 200
    assert "validated and saved" in response.text
    assert "secret-api-key" not in response.text
    assert master_key_store.path.exists()
    assert master_key_store.path.stat().st_mode & 0o777 == 0o600

    status_response = await client.get("/api/settings/ai")
    assert status_response.json()["configured"] is True
    assert status_response.json()["chat_model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_admin_update_rejects_invalid_csrf(client: AsyncClient):
    await _login_and_get_csrf(client)

    response = await client.post(
        "/admin/settings",
        data={
            "csrf_token": "invalid-token",
            "api_key": "secret-api-key",
            "chat_model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_model_update_preserves_the_existing_api_key(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(
        AIConfigurationService,
        "_validate_openai",
        AsyncMock(return_value=None),
    )
    csrf_token = await _login_and_get_csrf(client)
    initial_response = await client.post(
        "/admin/settings",
        data={
            "csrf_token": csrf_token,
            "api_key": "secret-api-key",
            "chat_model": "gpt-4o-mini",
        },
    )
    assert initial_response.status_code == 200

    update_response = await client.post(
        "/admin/settings",
        data={
            "csrf_token": csrf_token,
            "api_key": "",
            "chat_model": "gpt-4o",
        },
    )

    assert update_response.status_code == 200
    status_response = await client.get("/api/settings/ai")
    assert status_response.json()["chat_model"] == "gpt-4o"
    assert status_response.json()["api_key_configured"] is True


def test_production_rejects_missing_stable_secrets(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "admin_password", "")
    monkeypatch.setattr(settings, "admin_password_hash", "")
    monkeypatch.setattr(settings, "admin_session_secret", "")
    monkeypatch.setattr(settings, "encryption_key", "")

    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        validate_security_settings()
