"""
Tests for the ClickUp webhook router.

Covers:
- HMAC signature verification (valid, invalid, missing secret, empty signature)
- Event filtering (taskTagUpdated vs other events, ai-agent tag presence)
- Webhook deduplication (_DedupeCache: duplicate detection, TTL, capacity eviction)
- Malformed JSON handling
- _extract_task_id_from_branch helper (from callbacks.py, used across routers)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_hmac(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 hex digest matching ClickUp's webhook signature format."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _make_tag_updated_payload(
    task_id: str = "abc123",
    tag_name: str = "ai-agent",
    event: str = "taskTagUpdated",
    webhook_id: str = "wh-test-001",
) -> dict[str, Any]:
    """Build a minimal ClickUp taskTagUpdated payload with ai-agent tag."""
    return {
        "event": event,
        "webhook_id": webhook_id,
        "task_id": task_id,
        "history_items": [
            {
                "field": "tag",
                "after": {"name": tag_name, "tag_fg": "#ffffff"},
            }
        ],
    }


def _post_clickup(
    client: TestClient,
    payload: dict[str, Any],
    secret: str = "test-webhook-secret",
    *,
    include_signature: bool = True,
) -> Any:
    """POST to the ClickUp webhook endpoint with proper HMAC signature."""
    body = json.dumps(payload).encode()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if include_signature:
        headers["X-Signature"] = _compute_hmac(body, secret)
    return client.post("/webhooks/clickup", content=body, headers=headers)


# ── Reset dedupe cache between tests ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_dedupe_cache() -> None:
    """Reset the module-level dedupe cache before each test to prevent cross-test leaks.

    Setting _dedupe to None forces re-initialization on next access, which also
    picks up any env var changes made by monkeypatch in individual tests.
    """
    import apps.orchestrator.routers.clickup as clickup_module
    clickup_module._dedupe = None


# ── 1. Valid webhook with correct HMAC signature returns dispatching ──────────

class TestValidWebhook:
    """A properly signed taskTagUpdated event with ai-agent tag is dispatched."""

    def test_valid_webhook_returns_dispatching(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        payload = _make_tag_updated_payload(task_id="task-valid-001")
        resp = _post_clickup(client, payload, secret=env_vars["CLICKUP_WEBHOOK_SECRET"])

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "dispatching"
        assert data["task_id"] == "task-valid-001"

    def test_valid_webhook_with_different_task_id(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        payload = _make_tag_updated_payload(task_id="86bx3m")
        resp = _post_clickup(client, payload, secret=env_vars["CLICKUP_WEBHOOK_SECRET"])

        assert resp.status_code == 200
        assert resp.json()["action"] == "dispatching"
        assert resp.json()["task_id"] == "86bx3m"


# ── 2. Invalid HMAC signature returns 401 ────────────────────────────────────

class TestInvalidSignature:
    """Requests with wrong or tampered signatures are rejected."""

    def test_wrong_secret_returns_401(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        payload = _make_tag_updated_payload()
        resp = _post_clickup(client, payload, secret="wrong-secret-value")

        assert resp.status_code == 401
        assert "Invalid webhook signature" in resp.json()["detail"]

    def test_tampered_body_returns_401(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        """Signature computed for one body, but a different body is sent."""
        payload = _make_tag_updated_payload(task_id="original")
        original_body = json.dumps(payload).encode()
        signature = _compute_hmac(original_body, env_vars["CLICKUP_WEBHOOK_SECRET"])

        tampered_payload = _make_tag_updated_payload(task_id="tampered")
        tampered_body = json.dumps(tampered_payload).encode()

        resp = client.post(
            "/webhooks/clickup",
            content=tampered_body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature,
            },
        )
        assert resp.status_code == 401

    def test_missing_x_signature_header_returns_401(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        """When CLICKUP_WEBHOOK_SECRET is set but no X-Signature header is provided."""
        payload = _make_tag_updated_payload()
        body = json.dumps(payload).encode()
        resp = client.post(
            "/webhooks/clickup",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401


# ── 3. Missing CLICKUP_WEBHOOK_SECRET allows request (logs warning) ──────────

class TestMissingWebhookSecret:
    """When CLICKUP_WEBHOOK_SECRET is unset, signature verification is skipped."""

    def test_no_secret_allows_request(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, env_vars: dict[str, str]
    ) -> None:
        monkeypatch.delenv("CLICKUP_WEBHOOK_SECRET")
        payload = _make_tag_updated_payload(task_id="no-secret-task")
        body = json.dumps(payload).encode()

        resp = client.post(
            "/webhooks/clickup",
            content=body,
            headers={"Content-Type": "application/json"},
            # No X-Signature header at all
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "dispatching"

    def test_no_secret_logs_structured_warning(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, env_vars: dict[str, str]
    ) -> None:
        """Missing CLICKUP_WEBHOOK_SECRET logs a structured warning event, not a bare string."""
        import structlog.testing

        monkeypatch.delenv("CLICKUP_WEBHOOK_SECRET")
        payload = _make_tag_updated_payload(task_id="structured-warning-task")
        body = json.dumps(payload).encode()

        with structlog.testing.capture_logs() as logs:
            client.post(
                "/webhooks/clickup",
                content=body,
                headers={"Content-Type": "application/json"},
            )

        secret_warnings = [
            lg for lg in logs if lg.get("event") == "clickup_webhook_secret_not_set"
        ]
        assert len(secret_warnings) == 1
        assert secret_warnings[0]["log_level"] == "warning"
        assert "impact" in secret_warnings[0]

    def test_no_secret_allows_even_with_garbage_signature(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, env_vars: dict[str, str]
    ) -> None:
        monkeypatch.delenv("CLICKUP_WEBHOOK_SECRET")
        payload = _make_tag_updated_payload(task_id="garbage-sig-task")
        body = json.dumps(payload).encode()

        resp = client.post(
            "/webhooks/clickup",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": "totally-not-a-real-signature",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "dispatching"


# ── 4. Non-taskTagUpdated event returns ignored ──────────────────────────────

class TestEventFiltering:
    """Only taskTagUpdated events are processed; all others are acknowledged but ignored."""

    @pytest.mark.parametrize(
        "event_name",
        ["taskCreated", "taskUpdated", "taskDeleted", "taskCommentPosted", "taskStatusUpdated"],
    )
    def test_non_tag_update_events_are_ignored(
        self, client: TestClient, env_vars: dict[str, str], event_name: str
    ) -> None:
        payload = _make_tag_updated_payload(event=event_name)
        resp = _post_clickup(client, payload, secret=env_vars["CLICKUP_WEBHOOK_SECRET"])

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "ignored"
        assert event_name in data["reason"]

    def test_empty_event_is_ignored(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        payload = _make_tag_updated_payload(event="")
        resp = _post_clickup(client, payload, secret=env_vars["CLICKUP_WEBHOOK_SECRET"])

        assert resp.status_code == 200
        assert resp.json()["action"] == "ignored"


# ── 5. taskTagUpdated but no ai-agent tag returns ignored ────────────────────

class TestTagFiltering:
    """taskTagUpdated events are only dispatched if the ai-agent tag was added."""

    def test_different_tag_is_ignored(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        payload = _make_tag_updated_payload(tag_name="urgent")
        resp = _post_clickup(client, payload, secret=env_vars["CLICKUP_WEBHOOK_SECRET"])

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "ignored"
        assert data["reason"] == "ai_agent_tag_not_added"

    def test_empty_history_items_is_ignored(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        payload = {
            "event": "taskTagUpdated",
            "webhook_id": "wh-test-002",
            "task_id": "task-no-history",
            "history_items": [],
        }
        resp = _post_clickup(client, payload, secret=env_vars["CLICKUP_WEBHOOK_SECRET"])

        assert resp.status_code == 200
        assert resp.json()["reason"] == "ai_agent_tag_not_added"

    def test_history_item_with_no_after_field_is_ignored(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        payload = {
            "event": "taskTagUpdated",
            "webhook_id": "wh-test-003",
            "task_id": "task-no-after",
            "history_items": [
                {"field": "tag", "before": {"name": "ai-agent"}},
            ],
        }
        resp = _post_clickup(client, payload, secret=env_vars["CLICKUP_WEBHOOK_SECRET"])

        assert resp.status_code == 200
        assert resp.json()["reason"] == "ai_agent_tag_not_added"

    def test_history_item_with_after_not_dict_is_ignored(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        """after field is a string instead of a dict — should not match."""
        payload = {
            "event": "taskTagUpdated",
            "webhook_id": "wh-test-004",
            "task_id": "task-after-string",
            "history_items": [
                {"field": "tag", "after": "ai-agent"},
            ],
        }
        resp = _post_clickup(client, payload, secret=env_vars["CLICKUP_WEBHOOK_SECRET"])

        assert resp.status_code == 200
        assert resp.json()["reason"] == "ai_agent_tag_not_added"


# ── 6. Duplicate webhook (same task_id sent twice) returns ignored ───────────

class TestDeduplication:
    """The second identical webhook for the same task_id is deduplicated."""

    def test_duplicate_webhook_returns_ignored(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        payload = _make_tag_updated_payload(task_id="dup-task-001")
        secret = env_vars["CLICKUP_WEBHOOK_SECRET"]

        first_resp = _post_clickup(client, payload, secret=secret)
        assert first_resp.status_code == 200
        assert first_resp.json()["action"] == "dispatching"

        second_resp = _post_clickup(client, payload, secret=secret)
        assert second_resp.status_code == 200
        data = second_resp.json()
        assert data["action"] == "ignored"
        assert data["reason"] == "duplicate_event"

    def test_different_task_ids_are_not_duplicates(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        secret = env_vars["CLICKUP_WEBHOOK_SECRET"]

        payload_a = _make_tag_updated_payload(task_id="task-a")
        payload_b = _make_tag_updated_payload(task_id="task-b")

        resp_a = _post_clickup(client, payload_a, secret=secret)
        resp_b = _post_clickup(client, payload_b, secret=secret)

        assert resp_a.json()["action"] == "dispatching"
        assert resp_b.json()["action"] == "dispatching"


# ── 7. Malformed JSON body returns 400 ───────────────────────────────────────

class TestMalformedPayload:
    """Invalid JSON in the request body should return 400."""

    def test_invalid_json_returns_400(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        body = b"this is not json {{{{"
        signature = _compute_hmac(body, env_vars["CLICKUP_WEBHOOK_SECRET"])

        resp = client.post(
            "/webhooks/clickup",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature,
            },
        )
        assert resp.status_code == 400
        assert "Invalid JSON payload" in resp.json()["detail"]

    def test_empty_body_returns_400(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        body = b""
        signature = _compute_hmac(body, env_vars["CLICKUP_WEBHOOK_SECRET"])

        resp = client.post(
            "/webhooks/clickup",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature,
            },
        )
        assert resp.status_code == 400


# ── 8. _verify_clickup_signature: unit tests ────────────────────────────────

class TestVerifyClickupSignature:
    """Direct tests for the HMAC signature verification utility."""

    def test_valid_signature_returns_true(self) -> None:
        from apps.orchestrator.routers.clickup import _verify_clickup_signature

        body = b'{"event":"test"}'
        secret = "my-secret-key"
        signature = _compute_hmac(body, secret)

        assert _verify_clickup_signature(body, signature, secret) is True

    def test_invalid_signature_returns_false(self) -> None:
        from apps.orchestrator.routers.clickup import _verify_clickup_signature

        body = b'{"event":"test"}'
        secret = "my-secret-key"

        assert _verify_clickup_signature(body, "bad-hex-digest", secret) is False

    def test_empty_signature_returns_false(self) -> None:
        from apps.orchestrator.routers.clickup import _verify_clickup_signature

        body = b'{"event":"test"}'
        secret = "my-secret-key"

        assert _verify_clickup_signature(body, "", secret) is False

    def test_wrong_secret_returns_false(self) -> None:
        from apps.orchestrator.routers.clickup import _verify_clickup_signature

        body = b'{"event":"test"}'
        correct_secret = "correct-secret"
        wrong_secret = "wrong-secret"
        signature = _compute_hmac(body, correct_secret)

        assert _verify_clickup_signature(body, signature, wrong_secret) is False

    def test_signature_is_case_sensitive_hex(self) -> None:
        from apps.orchestrator.routers.clickup import _verify_clickup_signature

        body = b'{"event":"test"}'
        secret = "secret"
        signature = _compute_hmac(body, secret)

        # HMAC hexdigest is lowercase — uppercase should still match via compare_digest
        # since hexdigest() always returns lowercase, an uppercase version should not match
        assert _verify_clickup_signature(body, signature.upper(), secret) is False


# ── 9. _DedupeCache: unit tests ─────────────────────────────────────────────

class TestDedupeCache:
    """Direct tests for the in-memory deduplication cache."""

    def test_unseen_key_is_not_duplicate(self) -> None:
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache()
        assert cache.is_duplicate("new-key") is False

    def test_seen_key_is_duplicate(self) -> None:
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache()
        cache.mark_seen("key-1")
        assert cache.is_duplicate("key-1") is True

    def test_mark_seen_then_duplicate(self) -> None:
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache()
        cache.mark_seen("alpha")
        cache.mark_seen("beta")

        assert cache.is_duplicate("alpha") is True
        assert cache.is_duplicate("beta") is True
        assert cache.is_duplicate("gamma") is False

    def test_capacity_eviction_removes_oldest(self) -> None:
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache(max_size=3, ttl_seconds=3600)
        cache.mark_seen("a")
        cache.mark_seen("b")
        cache.mark_seen("c")
        cache.mark_seen("d")  # should evict "a"

        assert cache.is_duplicate("a") is False  # evicted
        assert cache.is_duplicate("b") is True
        assert cache.is_duplicate("c") is True
        assert cache.is_duplicate("d") is True

    def test_capacity_eviction_respects_insertion_order(self) -> None:
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache(max_size=2, ttl_seconds=3600)
        cache.mark_seen("first")
        cache.mark_seen("second")
        cache.mark_seen("third")  # evicts "first"
        cache.mark_seen("fourth")  # evicts "second"

        assert cache.is_duplicate("first") is False
        assert cache.is_duplicate("second") is False
        assert cache.is_duplicate("third") is True
        assert cache.is_duplicate("fourth") is True

    def test_ttl_expiry_makes_key_not_duplicate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache(max_size=100, ttl_seconds=60)

        # Mark seen at time T
        fake_time = 1000.0
        monkeypatch.setattr(time, "time", lambda: fake_time)
        cache.mark_seen("expiring-key")
        assert cache.is_duplicate("expiring-key") is True

        # Advance past TTL
        fake_time = 1061.0  # 61 seconds later, past the 60s TTL
        monkeypatch.setattr(time, "time", lambda: fake_time)
        assert cache.is_duplicate("expiring-key") is False

    def test_ttl_not_yet_expired_is_still_duplicate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache(max_size=100, ttl_seconds=60)

        fake_time = 1000.0
        monkeypatch.setattr(time, "time", lambda: fake_time)
        cache.mark_seen("key")

        # Advance but NOT past TTL
        fake_time = 1059.0  # 59 seconds later, still within 60s TTL
        monkeypatch.setattr(time, "time", lambda: fake_time)
        assert cache.is_duplicate("key") is True

    def test_expired_entry_is_removed_from_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After TTL expiry, is_duplicate removes the expired entry from the internal dict."""
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache(max_size=100, ttl_seconds=10)

        fake_time = 1000.0
        monkeypatch.setattr(time, "time", lambda: fake_time)
        cache.mark_seen("cleanup-key")
        assert "cleanup-key" in cache._cache

        fake_time = 1011.0
        monkeypatch.setattr(time, "time", lambda: fake_time)
        cache.is_duplicate("cleanup-key")  # triggers removal
        assert "cleanup-key" not in cache._cache

    def test_re_marking_after_expiry_refreshes_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from apps.orchestrator.routers.clickup import _DedupeCache

        cache = _DedupeCache(max_size=100, ttl_seconds=60)

        # Mark at T=1000
        fake_time = 1000.0
        monkeypatch.setattr(time, "time", lambda: fake_time)
        cache.mark_seen("refresh-key")

        # Expire at T=1061
        fake_time = 1061.0
        monkeypatch.setattr(time, "time", lambda: fake_time)
        assert cache.is_duplicate("refresh-key") is False

        # Re-mark at T=1061
        cache.mark_seen("refresh-key")
        assert cache.is_duplicate("refresh-key") is True

        # Still valid at T=1120 (59s after re-mark)
        fake_time = 1120.0
        monkeypatch.setattr(time, "time", lambda: fake_time)
        assert cache.is_duplicate("refresh-key") is True


# ── 10. _extract_task_id_from_branch ─────────────────────────────────────────

class TestExtractTaskIdFromBranch:
    """Tests for extracting ClickUp task IDs from branch names."""

    def test_standard_agent_branch(self) -> None:
        from apps.orchestrator.routers.callbacks import _extract_task_id_from_branch

        assert _extract_task_id_from_branch("agent/cu-abc123def") == "abc123def"

    def test_short_task_id(self) -> None:
        from apps.orchestrator.routers.callbacks import _extract_task_id_from_branch

        assert _extract_task_id_from_branch("agent/cu-86bx3m") == "86bx3m"

    def test_main_branch_returns_empty(self) -> None:
        from apps.orchestrator.routers.callbacks import _extract_task_id_from_branch

        assert _extract_task_id_from_branch("main") == ""

    def test_empty_string_returns_empty(self) -> None:
        from apps.orchestrator.routers.callbacks import _extract_task_id_from_branch

        assert _extract_task_id_from_branch("") == ""

    def test_feature_branch_without_cu_prefix_returns_empty(self) -> None:
        from apps.orchestrator.routers.callbacks import _extract_task_id_from_branch

        assert _extract_task_id_from_branch("feature/add-logging") == ""

    def test_nested_path_with_cu_prefix(self) -> None:
        from apps.orchestrator.routers.callbacks import _extract_task_id_from_branch

        assert _extract_task_id_from_branch("some/nested/cu-xyz789") == "xyz789"

    def test_cu_prefix_only_returns_empty_id(self) -> None:
        from apps.orchestrator.routers.callbacks import _extract_task_id_from_branch

        # "cu-" with nothing after it returns empty string (the [3:] slice)
        assert _extract_task_id_from_branch("agent/cu-") == ""

    def test_branch_with_no_slash(self) -> None:
        from apps.orchestrator.routers.callbacks import _extract_task_id_from_branch

        assert _extract_task_id_from_branch("cu-abc123") == "abc123"


# ── 11. _DedupeCache env var configuration ───────────────────────────────────

class TestDedupeCacheConfiguration:
    """DEDUP_CACHE_MAX_SIZE and DEDUP_CACHE_TTL_SECONDS configure the cache at init time."""

    def test_custom_max_size_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.setenv("DEDUP_CACHE_MAX_SIZE", "5")
        cache = clickup_module._get_dedupe_cache()
        assert cache._max_size == 5

    def test_custom_ttl_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.setenv("DEDUP_CACHE_TTL_SECONDS", "120")
        cache = clickup_module._get_dedupe_cache()
        assert cache._ttl == 120

    def test_default_max_size_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.delenv("DEDUP_CACHE_MAX_SIZE", raising=False)
        cache = clickup_module._get_dedupe_cache()
        assert cache._max_size == 1000

    def test_default_ttl_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.delenv("DEDUP_CACHE_TTL_SECONDS", raising=False)
        cache = clickup_module._get_dedupe_cache()
        assert cache._ttl == 3600

    def test_invalid_max_size_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.setenv("DEDUP_CACHE_MAX_SIZE", "not-a-number")
        cache = clickup_module._get_dedupe_cache()
        assert cache._max_size == 1000

    def test_invalid_ttl_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.setenv("DEDUP_CACHE_TTL_SECONDS", "abc")
        cache = clickup_module._get_dedupe_cache()
        assert cache._ttl == 3600

    def test_empty_max_size_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.setenv("DEDUP_CACHE_MAX_SIZE", "")
        cache = clickup_module._get_dedupe_cache()
        assert cache._max_size == 1000

    def test_empty_ttl_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.setenv("DEDUP_CACHE_TTL_SECONDS", "")
        cache = clickup_module._get_dedupe_cache()
        assert cache._ttl == 3600

    def test_configured_max_size_enforced_on_eviction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cache initialized with MAX_SIZE=2 evicts oldest on the 3rd entry."""
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.setenv("DEDUP_CACHE_MAX_SIZE", "2")
        cache = clickup_module._get_dedupe_cache()

        cache.mark_seen("x")
        cache.mark_seen("y")
        cache.mark_seen("z")  # evicts "x"

        assert cache.is_duplicate("x") is False
        assert cache.is_duplicate("y") is True
        assert cache.is_duplicate("z") is True

    def test_configured_ttl_enforced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A cache initialized with TTL=10 expires keys after 10 seconds."""
        import apps.orchestrator.routers.clickup as clickup_module

        monkeypatch.setenv("DEDUP_CACHE_TTL_SECONDS", "10")
        cache = clickup_module._get_dedupe_cache()

        fake_time = 2000.0
        monkeypatch.setattr(time, "time", lambda: fake_time)
        cache.mark_seen("ttl-test-key")
        assert cache.is_duplicate("ttl-test-key") is True

        fake_time = 2011.0  # 11 seconds later, past the 10s TTL
        assert cache.is_duplicate("ttl-test-key") is False
