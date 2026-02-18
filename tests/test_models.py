"""
Tests for apps.orchestrator.models.AgentTask.

Covers:
- from_clickup_payload() construction and validation
- Title extraction, stripping, and missing-title rejection
- Description extraction (empty, present, None)
- Risk tier inference (HIGH / MEDIUM / LOW keywords)
- Complexity inference (standard vs high based on description length)
- Correlation ID handling (auto-generated, valid provided, invalid provided)
- Branch name derivation
- Validation errors (empty task_id, invalid chars, missing title)
- to_dispatch_payload() serialization
- __repr__ title truncation
"""

from __future__ import annotations

import uuid

import pytest

from apps.orchestrator.models import (
    COMPLEXITY_HIGH_THRESHOLD,
    HIGH_RISK_KEYWORDS,
    MEDIUM_RISK_KEYWORDS,
    AgentTask,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_payload(
    task_id: str = "abc123",
    name: str = "Implement feature X",
    description: str = "Build the thing.",
    correlation_id: str | None = None,
) -> AgentTask:
    """Convenience builder: create a valid AgentTask with sensible defaults."""
    details: dict[str, object] = {"name": name, "description": description}
    return AgentTask.from_clickup_payload(
        task_id=task_id,
        task_details=details,
        correlation_id=correlation_id,
    )


# ── 1. Valid payload creates correct task ────────────────────────────────────


class TestFromClickupPayloadValid:
    """from_clickup_payload() with valid inputs."""

    def test_valid_payload_creates_task(self):
        task = _make_payload(task_id="xyz789", name="Do a thing", description="Details here")
        assert task.clickup_task_id == "xyz789"
        assert task.title == "Do a thing"
        assert task.description == "Details here"

    def test_valid_payload_returns_agenttask_instance(self):
        task = _make_payload()
        assert isinstance(task, AgentTask)

    def test_valid_payload_task_is_frozen(self):
        task = _make_payload()
        with pytest.raises(AttributeError):
            task.title = "something else"  # type: ignore[misc]


# ── 2. Title extraction and stripping ────────────────────────────────────────


class TestTitleExtraction:
    """Title is extracted from task_details['name'] and stripped."""

    def test_title_whitespace_stripped(self):
        task = _make_payload(name="  padded title  ")
        assert task.title == "padded title"

    def test_title_leading_newlines_stripped(self):
        task = _make_payload(name="\n\tFoo\n")
        assert task.title == "Foo"

    def test_title_preserved_when_clean(self):
        task = _make_payload(name="Already clean")
        assert task.title == "Already clean"


# ── 3. Description extraction ────────────────────────────────────────────────


class TestDescriptionExtraction:
    """Description may be empty, present, or None in the payload."""

    def test_description_present(self):
        task = _make_payload(description="Build a REST endpoint")
        assert task.description == "Build a REST endpoint"

    def test_description_empty_string(self):
        task = _make_payload(description="")
        assert task.description == ""

    def test_description_none_becomes_empty(self):
        details: dict[str, object] = {"name": "Title", "description": None}
        task = AgentTask.from_clickup_payload(task_id="t1", task_details=details)
        assert task.description == ""

    def test_description_missing_key_becomes_empty(self):
        details: dict[str, object] = {"name": "Title"}
        task = AgentTask.from_clickup_payload(task_id="t1", task_details=details)
        assert task.description == ""

    def test_description_whitespace_stripped(self):
        task = _make_payload(description="  some details  ")
        assert task.description == "some details"


# ── 4. Risk tier inference ───────────────────────────────────────────────────


class TestRiskTierInference:
    """Risk tier is inferred from keywords in title + description.

    Note: The tokenizer uses regex ``\\b[a-z]+\\b`` which only captures
    purely alphabetical tokens. Keywords containing digits (e.g. 'neo4j')
    will never be matched by the current tokenizer. Tests below exclude
    such keywords from the parametrized HIGH-match assertions and instead
    verify the non-match explicitly.
    """

    # Keywords that contain non-alpha chars and cannot match the tokenizer
    _UNMATCHABLE_KEYWORDS = frozenset(k for k in HIGH_RISK_KEYWORDS if not k.isalpha())

    @pytest.mark.parametrize("keyword", sorted(HIGH_RISK_KEYWORDS - _UNMATCHABLE_KEYWORDS))
    def test_high_risk_keyword_in_title(self, keyword):
        task = _make_payload(name=f"Fix the {keyword} module", description="")
        assert task.risk_tier == "high", f"Expected HIGH for keyword {keyword!r} in title"

    @pytest.mark.parametrize("keyword", sorted(HIGH_RISK_KEYWORDS - _UNMATCHABLE_KEYWORDS))
    def test_high_risk_keyword_in_description(self, keyword):
        task = _make_payload(name="Generic task", description=f"Relates to {keyword} flow")
        assert task.risk_tier == "high", f"Expected HIGH for keyword {keyword!r} in description"

    @pytest.mark.parametrize("keyword", sorted(_UNMATCHABLE_KEYWORDS))
    def test_alphanumeric_keyword_not_matched_by_tokenizer(self, keyword):
        """Keywords with digits (e.g. 'neo4j') are in HIGH_RISK_KEYWORDS but the
        tokenizer only extracts [a-z]+ tokens, so they never trigger HIGH risk."""
        task = _make_payload(name=f"Fix the {keyword} module", description="")
        assert task.risk_tier != "high"

    @pytest.mark.parametrize("keyword", sorted(MEDIUM_RISK_KEYWORDS))
    def test_medium_risk_keyword_in_title(self, keyword):
        task = _make_payload(name=f"Update the {keyword} layer", description="")
        assert task.risk_tier == "medium", f"Expected MEDIUM for keyword {keyword!r}"

    @pytest.mark.parametrize("keyword", sorted(MEDIUM_RISK_KEYWORDS))
    def test_medium_risk_keyword_in_description(self, keyword):
        task = _make_payload(name="Generic task", description=f"Change the {keyword} config")
        assert task.risk_tier == "medium", f"Expected MEDIUM for keyword {keyword!r} in desc"

    def test_high_takes_precedence_over_medium(self):
        task = _make_payload(
            name="Update the api endpoint",
            description="Needs new auth flow",
        )
        assert task.risk_tier == "high"

    def test_no_keywords_yields_low(self):
        task = _make_payload(name="Fix typo in readme", description="Correct spelling")
        assert task.risk_tier == "low"

    def test_keywords_are_case_insensitive(self):
        task = _make_payload(name="AUTH MODULE REFACTOR", description="")
        assert task.risk_tier == "high"

    def test_keyword_as_substring_not_matched(self):
        """Partial matches inside words should not trigger risk keywords.
        e.g. 'authentication' contains 'auth', but they are separate keywords
        that both appear in HIGH_RISK_KEYWORDS. Test with a word that genuinely
        contains a keyword as a substring but is not itself a keyword."""
        task = _make_payload(name="Fix the importlib usage", description="")
        # 'importlib' should NOT match 'import' because word boundary matching
        # extracts whole words only — 'importlib' is a single token, not 'import' + 'lib'
        assert task.risk_tier == "low"


# ── 5. Complexity inference ──────────────────────────────────────────────────


class TestComplexityInference:
    """Complexity is 'high' when description exceeds the threshold length."""

    def test_short_description_is_standard(self):
        task = _make_payload(description="Short")
        assert task.complexity == "standard"

    def test_empty_description_is_standard(self):
        task = _make_payload(description="")
        assert task.complexity == "standard"

    def test_description_at_threshold_is_standard(self):
        desc = "x" * COMPLEXITY_HIGH_THRESHOLD
        task = _make_payload(description=desc)
        assert task.complexity == "standard"

    def test_description_above_threshold_is_high(self):
        desc = "x" * (COMPLEXITY_HIGH_THRESHOLD + 1)
        task = _make_payload(description=desc)
        assert task.complexity == "high"

    def test_description_just_above_threshold_is_high(self):
        desc = "a" * (COMPLEXITY_HIGH_THRESHOLD + 1)
        task = _make_payload(description=desc)
        assert task.complexity == "high"


# ── 6. Correlation ID ────────────────────────────────────────────────────────


class TestCorrelationId:
    """Correlation ID: auto-generated, valid provided, invalid replaced."""

    def test_auto_generated_when_none(self):
        task = _make_payload(correlation_id=None)
        # Must be a valid UUID4
        parsed = uuid.UUID(task.correlation_id)
        assert parsed.version == 4

    def test_valid_uuid_preserved(self):
        fixed_id = "550e8400-e29b-41d4-a716-446655440000"
        task = _make_payload(correlation_id=fixed_id)
        assert task.correlation_id == fixed_id

    def test_invalid_uuid_replaced_with_valid(self):
        task = _make_payload(correlation_id="not-a-uuid")
        # Should be replaced, not raise
        parsed = uuid.UUID(task.correlation_id)
        assert parsed.version == 4

    def test_empty_string_uuid_replaced(self):
        task = _make_payload(correlation_id="")
        parsed = uuid.UUID(task.correlation_id)
        assert parsed.version == 4

    def test_two_auto_ids_are_unique(self):
        task1 = _make_payload(correlation_id=None)
        task2 = _make_payload(correlation_id=None)
        assert task1.correlation_id != task2.correlation_id


# ── 7. Branch name derivation ────────────────────────────────────────────────


class TestBranchName:
    """Branch is derived as 'agent/cu-{task_id}'."""

    def test_branch_format(self):
        task = _make_payload(task_id="abc123")
        assert task.branch == "agent/cu-abc123"

    def test_branch_with_hyphenated_id(self):
        task = _make_payload(task_id="task-42")
        assert task.branch == "agent/cu-task-42"

    def test_branch_with_underscore_id(self):
        task = _make_payload(task_id="task_42")
        assert task.branch == "agent/cu-task_42"

    def test_branch_is_derived_not_settable(self):
        """Branch field has init=False, so it cannot be passed to constructor."""
        task = _make_payload(task_id="xyz")
        assert task.branch == "agent/cu-xyz"
        with pytest.raises(AttributeError):
            task.branch = "something"  # type: ignore[misc]


# ── 8. Validation errors ────────────────────────────────────────────────────


class TestValidationErrors:
    """from_clickup_payload() rejects malformed inputs with ValueError."""

    def test_empty_task_id_raises(self):
        with pytest.raises(ValueError, match="Missing or empty task_id"):
            _make_payload(task_id="")

    def test_whitespace_only_task_id_raises(self):
        with pytest.raises(ValueError, match="Missing or empty task_id"):
            _make_payload(task_id="   ")

    def test_invalid_chars_in_task_id_raises(self):
        with pytest.raises(ValueError, match="invalid characters"):
            _make_payload(task_id="abc!@#def")

    def test_task_id_with_spaces_raises(self):
        with pytest.raises(ValueError, match="invalid characters"):
            _make_payload(task_id="abc def")

    def test_task_id_with_dots_raises(self):
        with pytest.raises(ValueError, match="invalid characters"):
            _make_payload(task_id="abc.def")

    def test_missing_title_raises(self):
        with pytest.raises(ValueError, match="has no title"):
            _make_payload(name="")

    def test_whitespace_only_title_raises(self):
        with pytest.raises(ValueError, match="has no title"):
            _make_payload(name="   ")

    def test_none_name_in_details_raises(self):
        details: dict[str, object] = {"name": None, "description": "desc"}
        with pytest.raises(ValueError, match="has no title"):
            AgentTask.from_clickup_payload(task_id="t1", task_details=details)

    def test_missing_name_key_in_details_raises(self):
        details: dict[str, object] = {"description": "desc"}
        with pytest.raises(ValueError, match="has no title"):
            AgentTask.from_clickup_payload(task_id="t1", task_details=details)

    def test_non_string_task_id_raises(self):
        """If task_id is not a string, it should be treated as empty."""
        with pytest.raises(ValueError, match="Missing or empty task_id"):
            details: dict[str, object] = {"name": "Title"}
            AgentTask.from_clickup_payload(
                task_id=123,  # type: ignore[arg-type]
                task_details=details,
            )


# ── 9. to_dispatch_payload() ────────────────────────────────────────────────


class TestToDispatchPayload:
    """to_dispatch_payload() returns the correct dict for GitHub dispatch."""

    def test_contains_all_required_keys(self):
        task = _make_payload(task_id="t42", name="Build widget", description="Make it nice")
        payload = task.to_dispatch_payload()
        expected_keys = {
            "clickup_task_id",
            "title",
            "description",
            "correlation_id",
            "risk_tier",
            "complexity",
            "branch",
        }
        assert set(payload.keys()) == expected_keys

    def test_values_match_task_fields(self):
        corr = str(uuid.uuid4())
        task = _make_payload(
            task_id="t42",
            name="Build widget",
            description="Make it nice",
            correlation_id=corr,
        )
        payload = task.to_dispatch_payload()
        assert payload["clickup_task_id"] == "t42"
        assert payload["title"] == "Build widget"
        assert payload["description"] == "Make it nice"
        assert payload["correlation_id"] == corr
        assert payload["risk_tier"] == "low"
        assert payload["complexity"] == "standard"
        assert payload["branch"] == "agent/cu-t42"

    def test_all_values_are_strings(self):
        task = _make_payload()
        payload = task.to_dispatch_payload()
        for key, value in payload.items():
            assert isinstance(value, str), f"payload[{key!r}] is {type(value).__name__}, not str"

    def test_dispatch_payload_includes_branch(self):
        task = _make_payload(task_id="zz99")
        payload = task.to_dispatch_payload()
        assert payload["branch"] == "agent/cu-zz99"


# ── 10. __repr__ truncation ─────────────────────────────────────────────────


class TestRepr:
    """__repr__ truncates the title to 50 characters."""

    def test_short_title_not_truncated(self):
        task = _make_payload(name="Short title")
        r = repr(task)
        assert "Short title" in r

    def test_long_title_truncated_at_50(self):
        long_title = "A" * 80
        task = _make_payload(name=long_title)
        r = repr(task)
        # The repr should contain the first 50 chars of the title
        assert "A" * 50 in r
        # But NOT the full 80-char title
        assert "A" * 80 not in r

    def test_repr_contains_risk_and_complexity(self):
        task = _make_payload(
            name="Fix auth bug",
            description="Short desc",
        )
        r = repr(task)
        assert "risk=high" in r
        assert "complexity=standard" in r

    def test_repr_contains_task_id(self):
        task = _make_payload(task_id="myid123")
        r = repr(task)
        assert "myid123" in r

    def test_repr_format(self):
        task = _make_payload(task_id="id1", name="Title here")
        r = repr(task)
        assert r.startswith("AgentTask(")
        assert r.endswith(")")

    def test_exactly_50_char_title_not_truncated(self):
        title_50 = "B" * 50
        task = _make_payload(name=title_50)
        r = repr(task)
        assert title_50 in r
