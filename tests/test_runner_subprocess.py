"""Tests for apps.runner.engines.subprocess_util — async subprocess runner."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.runner.engines.subprocess_util import (
    OUTPUT_TAIL_LIMIT,
    SubprocessResult,
    _now_ms,
    run_engine_subprocess,
    tail,
)

# ── SubprocessResult ─────────────────────────────────────────────────────────


class TestSubprocessResult:
    """Tests for the result dataclass."""

    def test_frozen(self):
        result = SubprocessResult(
            return_code=0,
            stdout="ok",
            stderr="",
            duration_ms=100,
            timed_out=False,
        )
        with pytest.raises(AttributeError):
            result.return_code = 1

    def test_all_fields(self):
        result = SubprocessResult(
            return_code=1,
            stdout="output",
            stderr="err",
            duration_ms=5000,
            timed_out=True,
        )
        assert result.return_code == 1
        assert result.stdout == "output"
        assert result.stderr == "err"
        assert result.duration_ms == 5000
        assert result.timed_out is True

    def test_cancelled_default_false(self):
        result = SubprocessResult(
            return_code=0,
            stdout="",
            stderr="",
            duration_ms=0,
            timed_out=False,
        )
        assert result.cancelled is False


# ── tail ─────────────────────────────────────────────────────────────────────


class TestTail:
    """Tests for output tail utility."""

    def test_short_text_unchanged(self):
        assert tail("hello", limit=100) == "hello"

    def test_empty_text(self):
        assert tail("", limit=100) == ""

    def test_exact_limit(self):
        text = "a" * 100
        assert tail(text, limit=100) == text

    def test_long_text_truncated(self):
        text = "x" * 200
        result = tail(text, limit=50)
        assert result.startswith("...truncated...")
        assert result.endswith("x" * 50)
        assert len(result) < 200

    def test_default_limit(self):
        text = "y" * (OUTPUT_TAIL_LIMIT + 1000)
        result = tail(text)
        assert result.startswith("...truncated...")
        assert result.endswith("y" * OUTPUT_TAIL_LIMIT)


# ── _now_ms ──────────────────────────────────────────────────────────────────


class TestNowMs:
    """Tests for timestamp utility."""

    def test_returns_int(self):
        result = _now_ms()
        assert isinstance(result, int)
        assert result > 0

    def test_monotonic(self):
        a = _now_ms()
        b = _now_ms()
        assert b >= a


# ── run_engine_subprocess ────────────────────────────────────────────────────

# Note: These tests mock asyncio.create_subprocess_exec which is safe
# (arguments passed as list, no shell interpolation).
_SUBPROCESS_CREATE = "asyncio.create_subprocess_exec"


class TestRunEngineSubprocess:
    """Tests for the async subprocess runner."""

    @pytest.mark.asyncio
    async def test_successful_run(self, tmp_path):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"hello output", b""))
        mock_proc.returncode = 0

        with patch(_SUBPROCESS_CREATE, return_value=mock_proc):
            result = await run_engine_subprocess(
                ["echo", "hello"],
                cwd=tmp_path,
            )

        assert result.return_code == 0
        assert result.stdout == "hello output"
        assert result.stderr == ""
        assert result.timed_out is False
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_failed_run(self, tmp_path):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"fatal error"))
        mock_proc.returncode = 1

        with patch(_SUBPROCESS_CREATE, return_value=mock_proc):
            result = await run_engine_subprocess(
                ["false"],
                cwd=tmp_path,
            )

        assert result.return_code == 1
        assert result.stderr == "fatal error"
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_timeout(self, tmp_path):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError)
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = -9  # killed by signal

        with patch(_SUBPROCESS_CREATE, return_value=mock_proc):
            result = await run_engine_subprocess(
                ["sleep", "999"],
                cwd=tmp_path,
                timeout_seconds=1,
            )

        assert result.timed_out is True
        assert result.return_code == -9
        assert "timeout" in result.stderr.lower()
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_command_not_found(self, tmp_path):
        with patch(
            _SUBPROCESS_CREATE,
            side_effect=FileNotFoundError("No such file"),
        ):
            result = await run_engine_subprocess(
                ["nonexistent-binary"],
                cwd=tmp_path,
            )

        assert result.return_code == -1
        assert "Command not found" in result.stderr
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_env_overrides(self, tmp_path):
        captured_env = {}

        async def mock_create(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"ok", b""))
            proc.returncode = 0
            return proc

        with patch(_SUBPROCESS_CREATE, side_effect=mock_create):
            await run_engine_subprocess(
                ["test"],
                cwd=tmp_path,
                env_overrides={"MY_VAR": "test_value"},
            )

        assert captured_env.get("MY_VAR") == "test_value"

    @pytest.mark.asyncio
    async def test_stdin_text(self, tmp_path):
        captured_input = None

        mock_proc = AsyncMock()

        async def mock_communicate(input=None):
            nonlocal captured_input
            captured_input = input
            return (b"processed", b"")

        mock_proc.communicate = mock_communicate
        mock_proc.returncode = 0

        with patch(_SUBPROCESS_CREATE, return_value=mock_proc):
            result = await run_engine_subprocess(
                ["cat"],
                cwd=tmp_path,
                stdin_text="hello input",
            )

        assert captured_input == b"hello input"
        assert result.stdout == "processed"

    @pytest.mark.asyncio
    async def test_null_returncode_defaults_to_zero(self, tmp_path):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = None  # Some processes return None

        with patch(_SUBPROCESS_CREATE, return_value=mock_proc):
            result = await run_engine_subprocess(
                ["test"],
                cwd=tmp_path,
            )

        assert result.return_code == 0

    @pytest.mark.asyncio
    async def test_cancel_event_terminates_process(self, tmp_path):
        """When cancel_event is set, subprocess is terminated."""
        cancel_event = asyncio.Event()

        mock_proc = AsyncMock()
        mock_proc.pid = 12345
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = -15  # SIGTERM

        # communicate hangs forever (simulates a long-running process)
        async def hang_forever(input=None):
            await asyncio.sleep(999)
            return (b"", b"")

        mock_proc.communicate = hang_forever

        async def set_cancel():
            await asyncio.sleep(0.05)
            cancel_event.set()

        with patch(_SUBPROCESS_CREATE, return_value=mock_proc):
            # Set cancel after a short delay
            asyncio.create_task(set_cancel())
            result = await run_engine_subprocess(
                ["sleep", "999"],
                cwd=tmp_path,
                timeout_seconds=60,
                cancel_event=cancel_event,
            )

        assert result.cancelled is True
        assert "cancelled" in result.stderr.lower()
        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_event_none_uses_original_path(self, tmp_path):
        """Without cancel_event, the original code path is used."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"output", b""))
        mock_proc.returncode = 0

        with patch(_SUBPROCESS_CREATE, return_value=mock_proc):
            result = await run_engine_subprocess(
                ["echo"],
                cwd=tmp_path,
                cancel_event=None,
            )

        assert result.return_code == 0
        assert result.cancelled is False
        assert result.stdout == "output"

    @pytest.mark.asyncio
    async def test_cancel_event_process_completes_before_cancel(self, tmp_path):
        """If process finishes before cancel_event, result is normal."""
        cancel_event = asyncio.Event()

        mock_proc = AsyncMock()
        mock_proc.pid = 12345
        mock_proc.returncode = 0

        # communicate returns immediately
        async def fast_complete(input=None):
            return (b"done", b"")

        mock_proc.communicate = fast_complete

        with patch(_SUBPROCESS_CREATE, return_value=mock_proc):
            result = await run_engine_subprocess(
                ["echo"],
                cwd=tmp_path,
                timeout_seconds=60,
                cancel_event=cancel_event,
            )

        assert result.cancelled is False
        assert result.stdout == "done"
        assert result.return_code == 0
