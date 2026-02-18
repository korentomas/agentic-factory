#!/usr/bin/env python3
"""
Extract patterns — convenience CLI wrapper for the pattern extraction job.

Calls apps.orchestrator.jobs.pattern_extraction.run_extraction() to analyze
agent outcomes from data/agent-outcomes.jsonl and write updated rules files
to .claude/rules/.

Usage:
    python scripts/extract_patterns.py
    # Or after pip install -e .:
    agentfactory-extract

Environment variables:
    OUTCOMES_PATH  — path to agent-outcomes.jsonl (default: data/agent-outcomes.jsonl)
    RULES_DIR      — path to rules output directory (default: .claude/rules)
"""

from __future__ import annotations

from apps.orchestrator.jobs.pattern_extraction import main

if __name__ == "__main__":
    main()
