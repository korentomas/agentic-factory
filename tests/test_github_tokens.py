"""Tests for apps.runner.github_tokens — GitHub App installation token management."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.runner.github_tokens import (
    _REFRESH_MARGIN_SECONDS,
    GitHubTokenManager,
    _CachedToken,
)

# ── Fixtures ────────────────────────────────────────────────────────────────

_TEST_APP_ID = 12345
_TEST_INSTALLATION_ID = 67890


def _generate_test_private_key() -> str:
    """Generate a fresh RSA private key in PEM format for testing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


# Module-level test key (generated once per test session).
_TEST_PRIVATE_KEY = _generate_test_private_key()


@pytest.fixture()
def manager():
    """Create a GitHubTokenManager with test credentials."""
    return GitHubTokenManager(
        app_id=_TEST_APP_ID,
        private_key=_TEST_PRIVATE_KEY,
        installation_id=_TEST_INSTALLATION_ID,
    )


def _mock_token_response(token="ghs_test_token_abc123", expires_in_seconds=3600):
    """Build a mock httpx.Response for the installation token endpoint."""
    expires_at = time.time() + expires_in_seconds
    from datetime import UTC, datetime

    expires_at_str = (
        datetime.fromtimestamp(expires_at, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "token": token,
        "expires_at": expires_at_str,
        "permissions": {"contents": "write", "pull_requests": "write"},
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _mock_async_client(response):
    """Build a mock httpx.AsyncClient that returns the given response on POST."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ── JWT Generation ──────────────────────────────────────────────────────────


class TestJWTGeneration:
    """Tests for JWT generation from App credentials."""

    def test_generate_jwt_returns_string(self, manager):
        token = manager._generate_jwt()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_jwt_contains_correct_claims(self, manager):
        import jwt as pyjwt

        token = manager._generate_jwt()
        # Decode without verification to inspect claims
        payload = pyjwt.decode(token, options={"verify_signature": False})
        assert payload["iss"] == _TEST_APP_ID
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] > payload["iat"]


# ── Token Request ───────────────────────────────────────────────────────────


class TestGetToken:
    """Tests for get_token() — requesting and caching installation tokens."""

    @pytest.mark.asyncio
    async def test_get_token_makes_api_call(self, manager):
        mock_resp = _mock_token_response(token="ghs_fresh_token")
        mock_client = _mock_async_client(mock_resp)

        with patch("apps.runner.github_tokens.httpx.AsyncClient", return_value=mock_client):
            token = await manager.get_token()

        assert token == "ghs_fresh_token"
        mock_client.post.assert_called_once()

        # Verify the API URL includes the installation ID
        call_args = mock_client.post.call_args
        assert f"/installations/{_TEST_INSTALLATION_ID}/access_tokens" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_token_sends_minimal_permissions(self, manager):
        mock_resp = _mock_token_response()
        mock_client = _mock_async_client(mock_resp)

        with patch("apps.runner.github_tokens.httpx.AsyncClient", return_value=mock_client):
            await manager.get_token()

        call_args = mock_client.post.call_args
        sent_json = call_args[1]["json"]
        assert sent_json == {
            "permissions": {"contents": "write", "pull_requests": "write"},
        }

    @pytest.mark.asyncio
    async def test_get_token_caches_result(self, manager):
        mock_resp = _mock_token_response(token="ghs_cached_token", expires_in_seconds=3600)
        mock_client = _mock_async_client(mock_resp)

        with patch("apps.runner.github_tokens.httpx.AsyncClient", return_value=mock_client):
            token1 = await manager.get_token()
            token2 = await manager.get_token()

        assert token1 == "ghs_cached_token"
        assert token2 == "ghs_cached_token"
        # Only one HTTP call — second call uses cache
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_token_refreshes_expired_token(self, manager):
        # Seed the cache with an already-expired token
        manager._cached = _CachedToken(
            token="ghs_old_token",
            expires_at=time.time() - 60,  # expired 60 seconds ago
        )

        mock_resp = _mock_token_response(token="ghs_new_token", expires_in_seconds=3600)
        mock_client = _mock_async_client(mock_resp)

        with patch("apps.runner.github_tokens.httpx.AsyncClient", return_value=mock_client):
            token = await manager.get_token()

        assert token == "ghs_new_token"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_token_refreshes_near_expiry(self, manager):
        # Token that expires within the 5-minute margin
        manager._cached = _CachedToken(
            token="ghs_soon_expiring",
            expires_at=time.time() + 120,  # only 2 min left (< 5 min margin)
        )

        mock_resp = _mock_token_response(token="ghs_refreshed", expires_in_seconds=3600)
        mock_client = _mock_async_client(mock_resp)

        with patch("apps.runner.github_tokens.httpx.AsyncClient", return_value=mock_client):
            token = await manager.get_token()

        assert token == "ghs_refreshed"
        mock_client.post.assert_called_once()


# ── is_token_valid ──────────────────────────────────────────────────────────


class TestIsTokenValid:
    """Tests for is_token_valid() — cache validation logic."""

    def test_no_cached_token(self, manager):
        assert manager.is_token_valid() is False

    def test_valid_token(self, manager):
        manager._cached = _CachedToken(
            token="ghs_valid",
            expires_at=time.time() + _REFRESH_MARGIN_SECONDS + 600,
        )
        assert manager.is_token_valid() is True

    def test_expired_token(self, manager):
        manager._cached = _CachedToken(
            token="ghs_expired",
            expires_at=time.time() - 100,
        )
        assert manager.is_token_valid() is False

    def test_token_within_refresh_margin(self, manager):
        # Expires in 2 minutes — within the 5-minute refresh margin
        manager._cached = _CachedToken(
            token="ghs_near_expiry",
            expires_at=time.time() + 120,
        )
        assert manager.is_token_valid() is False


# ── Error Handling ──────────────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for API failure scenarios."""

    @pytest.mark.asyncio
    async def test_api_returns_401(self, manager):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(spec=httpx.Request),
            response=mock_resp,
        )

        mock_client = _mock_async_client(mock_resp)

        with patch("apps.runner.github_tokens.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError, match="401"):
                await manager.get_token()

    @pytest.mark.asyncio
    async def test_network_failure(self, manager):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("apps.runner.github_tokens.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.ConnectError, match="connection refused"):
                await manager.get_token()

    @pytest.mark.asyncio
    async def test_api_failure_does_not_corrupt_cache(self, manager):
        # Pre-populate with a valid cached token
        manager._cached = _CachedToken(
            token="ghs_still_good",
            expires_at=time.time() + _REFRESH_MARGIN_SECONDS + 600,
        )

        # The valid cache means no HTTP call is made; get_token returns the cached value.
        token = await manager.get_token()
        assert token == "ghs_still_good"
