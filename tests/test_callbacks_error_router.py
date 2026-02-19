"""Tests for ErrorRouter integration in callback handlers.

Verifies that:
- Failure/cancelled callbacks trigger ErrorRouter.handle()
- Success callbacks do NOT trigger ErrorRouter.handle()
- Blocked escalation callbacks trigger ErrorRouter.handle()
- Non-escalation blocked callbacks do NOT trigger ErrorRouter.handle()
- ErrorRouter failures never crash the callback response
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.orchestrator.routers.callbacks import router


@pytest.fixture()
def app() -> FastAPI:
    """Minimal FastAPI app with only the callbacks router mounted."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/callbacks")
    return test_app


class TestCallbacksErrorRouter:
    """Verify ErrorRouter is wired into the correct callback code paths."""

    @pytest.mark.asyncio
    async def test_failure_callback_triggers_error_router(self, app: FastAPI) -> None:
        """A failure callback should call ErrorRouter.handle() once."""
        mock_handle = AsyncMock()

        with (
            patch("apps.orchestrator.routers.callbacks._get_env", return_value=""),
            patch("apps.orchestrator.routers.callbacks._post_slack", new_callable=AsyncMock),
            patch(
                "apps.orchestrator.routers.callbacks._post_clickup_comment",
                new_callable=AsyncMock,
            ),
            patch("apps.orchestrator.routers.callbacks._error_router") as mock_router,
        ):
            mock_router.handle = mock_handle
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/callbacks/agent-complete",
                    json={
                        "clickup_task_id": "abc123",
                        "status": "failure",
                        "branch": "agent/cu-abc123",
                        "run_id": "12345",
                    },
                )
            assert resp.status_code == 200
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancelled_callback_triggers_error_router(self, app: FastAPI) -> None:
        """A cancelled callback should also call ErrorRouter.handle()."""
        mock_handle = AsyncMock()

        with (
            patch("apps.orchestrator.routers.callbacks._get_env", return_value=""),
            patch("apps.orchestrator.routers.callbacks._post_slack", new_callable=AsyncMock),
            patch(
                "apps.orchestrator.routers.callbacks._post_clickup_comment",
                new_callable=AsyncMock,
            ),
            patch("apps.orchestrator.routers.callbacks._error_router") as mock_router,
        ):
            mock_router.handle = mock_handle
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/callbacks/agent-complete",
                    json={
                        "clickup_task_id": "abc123",
                        "status": "cancelled",
                        "branch": "agent/cu-abc123",
                        "run_id": "67890",
                    },
                )
            assert resp.status_code == 200
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_callback_does_not_trigger_error_router(self, app: FastAPI) -> None:
        """A success callback should NOT call ErrorRouter.handle()."""
        mock_handle = AsyncMock()

        with (
            patch("apps.orchestrator.routers.callbacks._get_env", return_value=""),
            patch("apps.orchestrator.routers.callbacks._post_slack", new_callable=AsyncMock),
            patch(
                "apps.orchestrator.routers.callbacks._post_clickup_comment",
                new_callable=AsyncMock,
            ),
            patch("apps.orchestrator.routers.callbacks._error_router") as mock_router,
        ):
            mock_router.handle = mock_handle
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/callbacks/agent-complete",
                    json={
                        "clickup_task_id": "abc123",
                        "status": "success",
                        "pr_url": "https://github.com/x/y/pull/1",
                    },
                )
            assert resp.status_code == 200
            mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocked_escalation_triggers_error_router(self, app: FastAPI) -> None:
        """A blocked callback with escalation=true should call ErrorRouter.handle()."""
        mock_handle = AsyncMock()

        with (
            patch("apps.orchestrator.routers.callbacks._get_env", return_value=""),
            patch("apps.orchestrator.routers.callbacks._post_slack", new_callable=AsyncMock),
            patch(
                "apps.orchestrator.routers.callbacks._post_clickup_comment",
                new_callable=AsyncMock,
            ),
            patch("apps.orchestrator.routers.callbacks._error_router") as mock_router,
        ):
            mock_router.handle = mock_handle
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/callbacks/blocked",
                    json={
                        "pr_url": "https://github.com/x/y/pull/1",
                        "pr_number": 42,
                        "branch": "agent/cu-abc",
                        "reason": "max-remediation-rounds",
                        "escalation": True,
                    },
                )
            assert resp.status_code == 200
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_blocked_max_remediation_reason_triggers_error_router(
        self, app: FastAPI,
    ) -> None:
        """reason='max-remediation-rounds' triggers ErrorRouter even without escalation flag."""
        mock_handle = AsyncMock()

        with (
            patch("apps.orchestrator.routers.callbacks._get_env", return_value=""),
            patch("apps.orchestrator.routers.callbacks._post_slack", new_callable=AsyncMock),
            patch(
                "apps.orchestrator.routers.callbacks._post_clickup_comment",
                new_callable=AsyncMock,
            ),
            patch("apps.orchestrator.routers.callbacks._error_router") as mock_router,
        ):
            mock_router.handle = mock_handle
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/callbacks/blocked",
                    json={
                        "pr_url": "https://github.com/x/y/pull/2",
                        "pr_number": 43,
                        "branch": "agent/cu-def",
                        "reason": "max-remediation-rounds",
                        "escalation": False,
                    },
                )
            assert resp.status_code == 200
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_blocked_non_escalation_does_not_trigger_error_router(
        self, app: FastAPI,
    ) -> None:
        """A non-escalation blocked callback should NOT call ErrorRouter.handle()."""
        mock_handle = AsyncMock()

        with (
            patch("apps.orchestrator.routers.callbacks._get_env", return_value=""),
            patch("apps.orchestrator.routers.callbacks._post_slack", new_callable=AsyncMock),
            patch(
                "apps.orchestrator.routers.callbacks._post_clickup_comment",
                new_callable=AsyncMock,
            ),
            patch("apps.orchestrator.routers.callbacks._error_router") as mock_router,
        ):
            mock_router.handle = mock_handle
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/callbacks/blocked",
                    json={
                        "pr_url": "https://github.com/x/y/pull/3",
                        "pr_number": 44,
                        "branch": "agent/cu-ghi",
                        "reason": "lint-errors",
                        "escalation": False,
                    },
                )
            assert resp.status_code == 200
            mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_router_failure_doesnt_crash_callback(self, app: FastAPI) -> None:
        """If ErrorRouter.handle() raises, the callback still returns 200."""
        mock_handle = AsyncMock(side_effect=RuntimeError("router broken"))

        with (
            patch("apps.orchestrator.routers.callbacks._get_env", return_value=""),
            patch("apps.orchestrator.routers.callbacks._post_slack", new_callable=AsyncMock),
            patch(
                "apps.orchestrator.routers.callbacks._post_clickup_comment",
                new_callable=AsyncMock,
            ),
            patch("apps.orchestrator.routers.callbacks._error_router") as mock_router,
        ):
            mock_router.handle = mock_handle
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/callbacks/agent-complete",
                    json={
                        "clickup_task_id": "abc123",
                        "status": "failure",
                        "run_id": "12345",
                    },
                )
            # Callback still returns 200 even if ErrorRouter fails
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_blocked_error_router_failure_doesnt_crash_callback(
        self, app: FastAPI,
    ) -> None:
        """If ErrorRouter.handle() raises on blocked/escalation, the callback still returns 200."""
        mock_handle = AsyncMock(side_effect=RuntimeError("router broken"))

        with (
            patch("apps.orchestrator.routers.callbacks._get_env", return_value=""),
            patch("apps.orchestrator.routers.callbacks._post_slack", new_callable=AsyncMock),
            patch(
                "apps.orchestrator.routers.callbacks._post_clickup_comment",
                new_callable=AsyncMock,
            ),
            patch("apps.orchestrator.routers.callbacks._error_router") as mock_router,
        ):
            mock_router.handle = mock_handle
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/callbacks/blocked",
                    json={
                        "pr_url": "https://github.com/x/y/pull/5",
                        "pr_number": 50,
                        "branch": "agent/cu-jkl",
                        "reason": "max-remediation-rounds",
                        "escalation": True,
                    },
                )
            assert resp.status_code == 200
