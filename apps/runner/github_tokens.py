"""Short-lived GitHub App installation token management.

Generates JWT tokens for GitHub App authentication and exchanges
them for scoped installation access tokens via GitHub's REST API.

Tokens are cached and automatically refreshed when within 5 minutes
of expiry, minimising API calls while ensuring fresh credentials.

Security: Tokens are granted minimal permissions (contents:write,
pull_requests:write) — just enough for the agent to push code and
create PRs.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import httpx
import jwt
import structlog

logger = structlog.get_logger()

# GitHub App JWT lifetime: 10 minutes (GitHub max).
_JWT_LIFETIME_SECONDS = 600
# Refresh installation tokens when within this many seconds of expiry.
_REFRESH_MARGIN_SECONDS = 300
# GitHub API base URL.
_GITHUB_API_URL = "https://api.github.com"
# Default HTTP timeout for GitHub API calls.
_HTTP_TIMEOUT_SECONDS = 15
# Minimal permissions for the installation token.
_TOKEN_PERMISSIONS: dict[str, str] = {
    "contents": "write",
    "pull_requests": "write",
}


def _get_env(key: str, default: str = "") -> str:
    """Read an environment variable at call time (never at import time)."""
    return os.getenv(key, default)


@dataclass
class _CachedToken:
    """Internal representation of a cached installation access token."""

    token: str
    expires_at: float  # Unix timestamp


@dataclass
class GitHubTokenManager:
    """Manages short-lived GitHub App installation access tokens.

    Generates a JWT signed with the App's private key, then exchanges it
    for an installation access token scoped to minimal permissions. Tokens
    are cached in memory and transparently refreshed when nearing expiry.

    Args:
        app_id:          GitHub App ID.
        private_key:     PEM-encoded RSA private key for the GitHub App.
        installation_id: GitHub App installation ID for the target org/repo.
    """

    app_id: int
    private_key: str
    installation_id: int
    _cached: _CachedToken | None = field(default=None, repr=False)

    def _generate_jwt(self) -> str:
        """Generate a short-lived JWT for GitHub App authentication.

        The JWT is signed with RS256 and has a 10-minute lifetime
        (the maximum GitHub allows).

        Returns:
            Encoded JWT string.
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # issued-at: 60 seconds in the past for clock skew
            "exp": now + _JWT_LIFETIME_SECONDS,
            "iss": self.app_id,
        }
        encoded: str = jwt.encode(payload, self.private_key, algorithm="RS256")
        logger.debug("github_tokens.jwt_generated", app_id=self.app_id)
        return encoded

    def is_token_valid(self) -> bool:
        """Check whether the cached installation token is still valid.

        A token is considered valid if it exists and will not expire
        within the next 5 minutes (_REFRESH_MARGIN_SECONDS).

        Returns:
            True if the cached token is usable, False otherwise.
        """
        if self._cached is None:
            return False
        return time.time() < (self._cached.expires_at - _REFRESH_MARGIN_SECONDS)

    async def _request_installation_token(self) -> _CachedToken:
        """Exchange a JWT for a scoped installation access token.

        Calls POST /app/installations/{id}/access_tokens with minimal
        permissions.

        Returns:
            A _CachedToken with the new token and its expiry time.

        Raises:
            httpx.HTTPStatusError: If the GitHub API returns an error status.
            httpx.RequestError:    If the HTTP request itself fails.
        """
        app_jwt = self._generate_jwt()
        url = f"{_GITHUB_API_URL}/app/installations/{self.installation_id}/access_tokens"

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"permissions": _TOKEN_PERMISSIONS},
            )
            response.raise_for_status()

        data = response.json()
        token = data["token"]
        # GitHub returns ISO 8601 expiry — parse to unix timestamp.
        # Format: "2024-01-15T12:00:00Z"
        expires_at_str: str = data["expires_at"]
        # Use time.mktime with a manual parse to avoid dateutil dependency.
        # GitHub always returns UTC in "YYYY-MM-DDTHH:MM:SSZ" format.
        from datetime import UTC, datetime

        expires_at_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        expires_at = expires_at_dt.replace(tzinfo=UTC).timestamp()

        logger.info(
            "github_tokens.installation_token_created",
            installation_id=self.installation_id,
            expires_at=expires_at_str,
        )
        return _CachedToken(token=token, expires_at=expires_at)

    async def get_token(self) -> str:
        """Return a valid installation access token, refreshing if needed.

        If the cached token is still valid, returns it immediately.
        Otherwise requests a fresh token from the GitHub API.

        Returns:
            A GitHub installation access token string.

        Raises:
            httpx.HTTPStatusError: If the GitHub API returns an error status.
            httpx.RequestError:    If the HTTP request itself fails.
        """
        if self.is_token_valid():
            logger.debug("github_tokens.cache_hit", installation_id=self.installation_id)
            return self._cached.token  # type: ignore[union-attr]

        logger.info(
            "github_tokens.refreshing",
            installation_id=self.installation_id,
            had_cached=self._cached is not None,
        )
        self._cached = await self._request_installation_token()
        return self._cached.token
