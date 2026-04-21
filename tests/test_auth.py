"""Unit tests for authentication middleware and token validation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.auth.middleware import AuthMiddleware
from src.auth.token_store import TokenInfo, validate_token


class TestValidateToken:
    @pytest.mark.asyncio()
    async def test_master_token_valid(self) -> None:
        with patch("src.auth.token_store.settings") as mock_settings:
            mock_settings.MASTER_TOKEN = "master-secret"
            with patch("src.auth.token_store.agent_registry") as mock_registry:
                mock_registry.list_agents = AsyncMock(return_value=[])
                result = await validate_token("master-secret")
                assert result is not None
                assert result.is_master is True
                assert result.agent_id is None

    @pytest.mark.asyncio()
    async def test_invalid_token_returns_none(self) -> None:
        with patch("src.auth.token_store.settings") as mock_settings:
            mock_settings.MASTER_TOKEN = "master-secret"
            with patch("src.auth.token_store.agent_registry") as mock_registry:
                mock_registry.list_agents = AsyncMock(return_value=[])
                result = await validate_token("wrong-token")
                assert result is None

    @pytest.mark.asyncio()
    async def test_agent_token_valid(self) -> None:
        mock_agent = type("Agent", (), {"token": "agent-tok-123", "id": "agent-1"})()
        with patch("src.auth.token_store.settings") as mock_settings:
            mock_settings.MASTER_TOKEN = "master-secret"
            with patch("src.auth.token_store.agent_registry") as mock_registry:
                mock_registry.list_agents = AsyncMock(return_value=[mock_agent])
                result = await validate_token("agent-tok-123")
                assert result is not None
                assert result.is_master is False
                assert result.agent_id == "agent-1"

    @pytest.mark.asyncio()
    async def test_empty_master_token_not_matched(self) -> None:
        with patch("src.auth.token_store.settings") as mock_settings:
            mock_settings.MASTER_TOKEN = ""
            with patch("src.auth.token_store.agent_registry") as mock_registry:
                mock_registry.list_agents = AsyncMock(return_value=[])
                result = await validate_token("")
                assert result is None


class TestTokenInfo:
    def test_frozen_dataclass(self) -> None:
        info = TokenInfo(token="t", agent_id=None, is_master=True)
        with pytest.raises(AttributeError):
            info.token = "new"  # type: ignore[misc]


def _make_test_app() -> FastAPI:
    """Create a minimal FastAPI app with AuthMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/admin/settings")
    async def admin_settings() -> dict:
        return {"setting": "value"}

    @app.post("/v1/chat/completions")
    async def completions() -> dict:
        return {"response": "ok"}

    return app


class TestAuthMiddleware:
    @pytest.fixture()
    def app(self) -> FastAPI:
        return _make_test_app()

    @pytest.mark.asyncio()
    async def test_public_endpoint_no_auth(self, app: FastAPI) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.get("/health")
            assert resp.status_code == 200

    @pytest.mark.asyncio()
    async def test_protected_endpoint_no_token_401(self, app: FastAPI) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.get("/admin/settings")
            assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_protected_endpoint_invalid_token_401(self, app: FastAPI) -> None:
        with patch(
            "src.auth.middleware.validate_token",
            new_callable=AsyncMock,
            return_value=None,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.get(
                    "/admin/settings",
                    headers={"Authorization": "Bearer invalid"},
                )
                assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_master_token_access_admin(self, app: FastAPI) -> None:
        master_info = TokenInfo(token="master", agent_id=None, is_master=True)
        with patch(
            "src.auth.middleware.validate_token",
            new_callable=AsyncMock,
            return_value=master_info,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.get(
                    "/admin/settings",
                    headers={"Authorization": "Bearer master"},
                )
                assert resp.status_code == 200

    @pytest.mark.asyncio()
    async def test_agent_token_access_completions(self, app: FastAPI) -> None:
        agent_info = TokenInfo(token="agent-tok", agent_id="a1", is_master=False)
        with patch(
            "src.auth.middleware.validate_token",
            new_callable=AsyncMock,
            return_value=agent_info,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": "Bearer agent-tok"},
                )
                assert resp.status_code == 200

    @pytest.mark.asyncio()
    async def test_agent_token_blocked_from_admin(self, app: FastAPI) -> None:
        agent_info = TokenInfo(token="agent-tok", agent_id="a1", is_master=False)
        with patch(
            "src.auth.middleware.validate_token",
            new_callable=AsyncMock,
            return_value=agent_info,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.get(
                    "/admin/settings",
                    headers={"Authorization": "Bearer agent-tok"},
                )
                assert resp.status_code == 403

    @pytest.mark.asyncio()
    async def test_malformed_auth_header_401(self, app: FastAPI) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            resp = await client.get(
                "/admin/settings",
                headers={"Authorization": "Basic dXNlcjpwYXNz"},
            )
            assert resp.status_code == 401
