import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analyze_repository_invalid_url(client: AsyncClient):
    response = await client.post("/api/repositories/analyze", json={
        "github_url": "not-a-url",
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_repository_missing_url(client: AsyncClient):
    response = await client.post("/api/repositories/analyze", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_repository_not_found(client: AsyncClient):
    response = await client.get("/api/repositories/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_analysis_not_found(client: AsyncClient):
    response = await client.get("/api/repositories/99999/overview")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_no_repository(client: AsyncClient):
    response = await client.post("/api/repositories/99999/chat", json={
        "question": "What does this project do?",
    })
    assert response.status_code == 404
