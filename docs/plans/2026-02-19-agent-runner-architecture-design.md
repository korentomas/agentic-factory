# Agent Runner Architecture

**Date**: 2026-02-19
**Status**: Draft
**Project**: LailaTov (formerly AgentFactory)

---

## Problem Statement

LailaTov runs coding agents inside GitHub Actions CI. This works, but it is fundamentally limiting in five ways:

### 1. Engine lock-in to GitHub Actions

Every coding engine needs a GitHub Action to participate in the pipeline. Currently supported engines:

| Engine | Has Official GitHub Action | Status |
|--------|---------------------------|--------|
| claude-code | Yes (`anthropics/claude-code-action@v1`) | Production |
| codex | Yes (`openai/codex-action@v1`) | Production |
| gemini-cli | Yes (`google-github-actions/run-gemini-cli@v1`) | Production |
| aider | Community only (`raphaelcastilhoc/aider-action@v1`) | Fragile, outdated |
| kimi-cli | No | Cannot use |
| qwen-code | No | Cannot use |
| swe-agent | No | Cannot use |
| Devon | No | Cannot use |

Four of the eight engines we want cannot run in CI at all. The workaround for DeepSeek and Qwen (routing through codex's action with alternative API endpoints) is brittle and loses engine-specific features.

### 2. GitHub Actions constraints

- **6-hour hard timeout**. Complex tasks on large codebases can exceed this. There is no way to pause, checkpoint, and resume.
- **No persistent state** between runs. Every run starts from a fresh checkout. Agent context, intermediate results, and warm caches are lost.
- **Limited compute**. Standard runners have 7 GB RAM and 2 vCPUs. No GPU. No control over runtime environment.
- **Cost opacity**. GitHub Actions minutes are billed separately from LLM API costs, making true cost-per-task hard to calculate.

### 3. Composite action complexity

The current `run-agent` composite action (`.github/actions/run-agent/action.yml`) is already 160 lines of YAML that dispatches to three engines with normalized outputs. Adding a fourth engine means another conditional block, another set of inputs, and more output normalization logic. YAML is the wrong language for this.

### 4. No engine experimentation

We cannot easily A/B test engines on the same task. We cannot route high-risk tasks to Claude and low-risk tasks to a cheaper engine at runtime. The engine is baked into CI workflow configuration, not runtime decisions.

### 5. No local development story

Developers cannot run the full pipeline locally. Testing a new engine adapter requires pushing to GitHub and waiting for CI. This makes engine development slow and expensive.

---

## Proposed Architecture

Pull agent execution out of CI into an **Agent Runner** service that the orchestrator controls directly.

```
GitHub Issue / ClickUp Ticket
    |
    v
[agent-triage.yml]       <-- remains in CI (lightweight, fast)
    |
    v
[Orchestrator]            <-- existing FastAPI service
    |
    v
[Agent Runner Service]    <-- NEW: receives task, runs engine, returns result
    |
    +-- checkout repo
    +-- select engine
    +-- run engine subprocess
    +-- capture structured output
    +-- commit + push
    +-- report result
    |
    v
[agent-review.yml]        <-- remains in CI (or also migrates later)
```

### Core Components

#### 1. Agent Runner HTTP Service

A FastAPI service that accepts task requests and executes coding agents.

```python
# apps/runner/main.py
app = FastAPI(title="LailaTov Agent Runner")

@app.post("/tasks")
async def execute_task(request: TaskRequest) -> TaskResult:
    """Accept a task, run a coding agent, return structured results."""
    ...
```

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/tasks` | Submit a new agent task |
| `GET` | `/tasks/{task_id}` | Poll task status |
| `POST` | `/tasks/{task_id}/cancel` | Cancel a running task |
| `GET` | `/health` | Health check |

#### 2. Task Lifecycle

```
PENDING -> RUNNING -> COMMITTING -> COMPLETE
                  \-> FAILED
                  \-> CANCELLED
                  \-> TIMED_OUT
```

The runner manages the full lifecycle: clone the repo, create a branch, run the engine, commit results, push, and report back. The orchestrator does not need to know engine internals.

#### 3. Workspace Management

Each task gets an isolated workspace:

```
/workspaces/{task_id}/
    repo/              # shallow clone of target repo
    output/            # engine output files
    logs/              # structured execution logs
```

Workspaces are cleaned up after result reporting (or after a configurable TTL for debugging). For future optimization, warm clones can be maintained per-repo and copied via `git worktree`.

---

## Engine Abstraction

A Python protocol that every engine adapter implements:

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class AgentTask:
    task_id: str
    title: str
    description: str
    repo_url: str
    branch: str
    risk_tier: str
    complexity: str
    workspace_path: Path
    model: str | None = None
    max_turns: int = 40

@dataclass(frozen=True)
class AgentResult:
    task_id: str
    status: Literal["success", "failure", "timeout", "cancelled"]
    files_changed: list[str]
    cost_usd: float
    num_turns: int
    duration_ms: int
    stdout: str
    stderr: str
    engine: str
    model: str

class AgentEngine(Protocol):
    """Interface that every engine adapter must implement."""

    @property
    def name(self) -> str:
        """Engine identifier (e.g. 'claude-code', 'aider', 'kimi-cli')."""
        ...

    @property
    def supported_models(self) -> list[str]:
        """Models this engine can run."""
        ...

    async def run(self, task: AgentTask) -> AgentResult:
        """Execute the task and return structured results."""
        ...

    async def check_available(self) -> bool:
        """Return True if the engine binary is installed and accessible."""
        ...
```

### Adapter Implementations

Each adapter wraps a CLI tool as a subprocess. The pattern is identical for all of them: build the command, set env vars, run it, parse output.

```python
class ClaudeCodeAdapter:
    """Wraps the `claude` CLI."""

    name = "claude-code"
    supported_models = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]

    async def run(self, task: AgentTask) -> AgentResult:
        cmd = [
            "claude", "--print",
            "--model", task.model or "claude-sonnet-4-6",
            "--max-turns", str(task.max_turns),
            "--output-format", "json",
        ]
        result = await run_subprocess(cmd, cwd=task.workspace_path, stdin=task.prompt)
        return self._parse_output(task, result)
```

### Planned Adapters

| Adapter | CLI Command | Install | Notes |
|---------|-------------|---------|-------|
| `ClaudeCodeAdapter` | `claude --print` | `npm i -g @anthropic-ai/claude-code` | Richest output (cost, turns, duration) |
| `CodexAdapter` | `codex --quiet` | `npm i -g @openai/codex` | Sandbox modes via `--sandbox` flag |
| `GeminiCliAdapter` | `gemini` | `npm i -g @anthropic-ai/gemini-cli` | Free tier with Google AI Studio key |
| `AiderAdapter` | `aider --yes-always` | `pip install aider-chat` | LiteLLM backend, any model |
| `KimiCliAdapter` | `kimi --quiet` | `npm i -g @anthropic-ai/kimi-cli` or binary | Moonshot/Kimi K2 |
| `QwenCodeAdapter` | `qwen-code -p` | Binary or pip | Alibaba Qwen Coder |
| `SweAgentAdapter` | `sweagent run` | `pip install sweagent` | Research-grade, benchmark SWE-bench |

### The aider Advantage

aider deserves special mention. It uses [LiteLLM](https://github.com/BerriAI/litellm) under the hood, which means a single adapter can reach nearly any model from any provider:

```python
class AiderAdapter:
    """Wraps aider CLI -- routes to any LiteLLM-supported model."""

    name = "aider"

    @property
    def supported_models(self) -> list[str]:
        # aider supports 100+ models via LiteLLM
        return ["*"]

    async def run(self, task: AgentTask) -> AgentResult:
        cmd = [
            "aider",
            "--yes-always",
            "--no-auto-commits",  # we handle commits ourselves
            "--model", task.model,
            "--message", task.prompt,
        ]
        ...
```

This makes aider the default fallback adapter. If a requested model does not have a dedicated engine, route it through aider.

### Engine Selection Logic

```python
def select_engine(model: str, preferred_engine: str | None = None) -> AgentEngine:
    """Pick the best engine for a given model.

    Priority:
    1. Explicit engine override (preferred_engine)
    2. Native engine for the model (claude-code for Claude, codex for GPT)
    3. aider as universal fallback
    """
    if preferred_engine:
        return get_engine(preferred_engine)

    # Native engine matching
    if model.startswith("claude-"):
        return ClaudeCodeAdapter()
    if model.startswith(("gpt-", "o1-", "o3")):
        return CodexAdapter()
    if model.startswith("gemini-"):
        return GeminiCliAdapter()
    if model.startswith("kimi-") or model.startswith("moonshot-"):
        return KimiCliAdapter()
    if model.startswith("qwen-"):
        return QwenCodeAdapter()

    # Universal fallback
    return AiderAdapter()
```

---

## Engine Comparison Table

Updated to include all engines, whether they need a GitHub Action, and how they work with the agent runner.

| Engine | Models | GitHub Action Required | Agent Runner (subprocess) | Cost Tracking | Turn Tracking | Best For |
|--------|--------|----------------------|--------------------------|---------------|---------------|----------|
| **claude-code** | Claude Opus/Sonnet/Haiku | `anthropics/claude-code-action@v1` | `claude --print` | Yes (Anthropic direct) | Yes | Primary coding, complex tasks |
| **codex** | GPT-4.1, o3 | `openai/codex-action@v1` | `codex --quiet` | No | No | OpenAI ecosystem, sandbox mode |
| **gemini-cli** | Gemini 2.5 Flash/Pro | `google-github-actions/run-gemini-cli@v1` | `gemini` | No | No | Free tier, Google ecosystem |
| **aider** | Any (via LiteLLM) | Community only | `aider --yes-always` | Yes (LiteLLM) | Yes | Universal fallback, model experiments |
| **kimi-cli** | Kimi K2, Moonshot | None | `kimi --quiet` | No | No | Chinese market, cost-effective |
| **qwen-code** | Qwen Coder, Qwen Max | None | `qwen-code -p` | No | No | Chinese market, Alibaba ecosystem |
| **swe-agent** | Any (configurable) | None | `sweagent run` | No | Yes | Benchmarking, research |

Key insight: **every engine in this table works as a subprocess**. Only three have GitHub Actions. The agent runner eliminates the GitHub Action requirement entirely.

---

## Hybrid Migration Path

We do not rewrite everything at once. The migration has three phases that can ship independently.

### Phase 1: Agent Runner as Alternative Path

**Goal**: Ship the runner. Keep CI working unchanged. Route specific tasks to the runner for validation.

```
                          +-- [CI: run-agent composite action]  (existing)
                         /
[Orchestrator] --+------+
                         \
                          +-- [Agent Runner: HTTP API]          (new)
```

**What changes:**
- New `apps/runner/` service with the engine abstraction and HTTP API
- Orchestrator gains a routing decision: `use_runner: bool` (controlled by env var or task metadata)
- When `use_runner=true`, orchestrator POSTs to the runner instead of dispatching to GitHub Actions
- CI workflows remain untouched as the default path

**What we validate:**
- Runner can clone, branch, run claude-code, commit, push, and create a PR
- Output matches what CI produces (same files_changed, same commit structure)
- Cost/turn tracking parity

**Effort**: 1-2 weeks

### Phase 2: CI Triggers Orchestrator, Orchestrator Delegates to Runner

**Goal**: CI becomes a thin trigger layer. The orchestrator owns all routing decisions.

```
[GitHub Event]
    |
    v
[agent-triage.yml]       <-- still in CI (just triage + dispatch)
    |
    v
[Orchestrator]
    |
    v
[Agent Runner]            <-- all execution happens here
    |
    +-- claude-code for high-risk
    +-- aider+deepseek for low-risk
    +-- gemini-cli for triage (free tier)
```

**What changes:**
- `agent-write.yml` becomes a 10-line workflow that calls the orchestrator's `/dispatch` endpoint and waits for a callback
- Engine selection moves from GitHub Actions vars (`WRITE_ENGINE`) to orchestrator config
- Orchestrator can now A/B test engines, implement cost-based routing, and retry with fallback engines at runtime
- All engine adapters (including kimi-cli, qwen-code, swe-agent) are available

**What we validate:**
- End-to-end: issue label -> triage -> orchestrator -> runner -> PR
- Fallback chains work (claude fails, retry with aider+sonnet)
- Cost tracking aggregated across plan + write + remediation steps

**Effort**: 1-2 weeks (after Phase 1 is stable)

### Phase 3: CI Becomes Thin Trigger Only

**Goal**: GitHub Actions only handles event detection and webhook delivery. Everything else is the runner.

```
[GitHub Event]
    |
    v
[Lightweight webhook handler]   <-- 5-line workflow or GitHub App webhook
    |
    v
[Orchestrator]                   <-- owns triage, routing, scheduling
    |
    v
[Agent Runner]                   <-- owns execution
    |
    v
[GitHub API]                     <-- commits, PRs, comments via API
```

**What changes:**
- Triage also moves to the runner (or becomes an orchestrator-internal step)
- Review and remediation loops happen inside the runner, not as separate CI jobs
- The full TRIAGE -> WRITE -> REVIEW -> REMEDIATE loop is a single orchestrator-managed workflow
- CI workflows are either deleted or reduced to a single `on: issues` trigger

**What we validate:**
- Full pipeline latency (eliminating CI queue wait times)
- Multi-round remediation without CI job overhead
- Persistent workspace across triage -> write -> review (no re-clone)

**Effort**: 2-3 weeks (after Phase 2 is stable)

---

## Infrastructure Options

Where the agent runner service runs. Evaluated on three criteria: cost at low volume (0-50 tasks/month), operational complexity, and execution constraints.

### Option A: Cloud Run (Recommended for Start)

| Aspect | Details |
|--------|---------|
| **How it works** | Container scales 0-N based on HTTP requests. Each task gets a container instance. |
| **Timeout** | Up to 60 minutes per request (configurable). For longer tasks, use Cloud Run Jobs (up to 24h). |
| **Cost at low volume** | Near-zero. Scale-to-zero means you pay only when tasks run. |
| **Compute** | Up to 8 vCPUs, 32 GB RAM per instance. No GPU. |
| **Disk** | Ephemeral filesystem. Use `/tmp` for workspaces (in-memory tmpfs on Cloud Run). For large repos, mount a Cloud Storage FUSE volume. |
| **Networking** | Outbound internet by default (for git clone, API calls). |
| **Ops burden** | Low. Managed platform. Deploy with `gcloud run deploy`. |

**Why this is the recommendation**: Zero cost when idle, scales automatically, 60-minute timeout covers most tasks, and we already need GCP for Vertex AI. Cloud Run Jobs extends this to 24 hours for edge cases.

### Option B: Fly.io

| Aspect | Details |
|--------|---------|
| **How it works** | Container runs in Fly Machines. Can scale to zero. |
| **Timeout** | No hard limit. Machines run until stopped. |
| **Cost at low volume** | Low. Machines API charges per-second. ~$0.02/hr for a small instance. |
| **Compute** | Up to 16 vCPUs, 256 GB RAM. GPU available. |
| **Disk** | Persistent volumes available (useful for warm repo clones). |
| **Ops burden** | Low-medium. `fly deploy`. Slightly more config than Cloud Run. |

**When to choose this**: If you need persistent disk for warm repo caches, or if you are not in the GCP ecosystem.

### Option C: Self-Hosted GitHub Actions Runner

| Aspect | Details |
|--------|---------|
| **How it works** | Standard GitHub Actions runner binary on your own VM. Workflows target `runs-on: self-hosted`. |
| **Timeout** | No GitHub-imposed limit (only your VM's uptime). |
| **Cost at low volume** | Cost of the VM (e.g. $5-20/mo for a small VPS). |
| **Compute** | Whatever your VM has. Full control. |
| **Disk** | Persistent. Warm clones survive across runs. |
| **Ops burden** | Medium-high. You manage the VM, updates, security, runner registration. |

**When to choose this**: If you want to keep the CI workflow model but remove GitHub's constraints. Does not solve the engine lock-in problem (still needs GitHub Actions for each engine). This option is a half-measure.

### Option D: Dedicated VM with Container Orchestration

| Aspect | Details |
|--------|---------|
| **How it works** | Docker containers on a VM, managed by Docker Compose or K3s. |
| **Timeout** | No limit. |
| **Cost** | VM cost. $20-100/mo depending on size. |
| **Compute** | Full control. GPU if needed. |
| **Ops burden** | High. You own everything. |

**When to choose this**: If you run at volume (100+ tasks/month) and need full control over scheduling, priorities, and resource allocation. Premature for early stages.

### Recommendation

Start with **Cloud Run** (Option A). It costs nothing when idle, deploys in minutes, and handles the 90th percentile of tasks within its timeout. Use Cloud Run Jobs for the long tail. Migrate to Fly.io or dedicated infra only if you hit Cloud Run's limits.

---

## Data Model

### TaskRequest (orchestrator -> runner)

```python
@dataclass(frozen=True)
class TaskRequest:
    task_id: str                    # e.g. "gh-42" or "cu-abc123"
    repo_url: str                   # e.g. "https://github.com/org/repo"
    branch: str                     # e.g. "agent/cu-gh-42"
    base_branch: str                # e.g. "main"
    title: str
    description: str
    risk_tier: Literal["high", "medium", "low"]
    complexity: Literal["high", "standard"]
    engine: str | None = None       # override engine selection
    model: str | None = None        # override model selection
    max_turns: int = 40
    timeout_seconds: int = 3600     # default 1 hour
    env_vars: dict[str, str] = field(default_factory=dict)
    constitution: str = ""          # CLAUDE.md contents (or path)
    callback_url: str | None = None # where to POST result
```

### TaskResult (runner -> orchestrator)

```python
@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: Literal["success", "failure", "timeout", "cancelled"]
    engine: str                     # which engine actually ran
    model: str                      # which model actually ran
    files_changed: list[str]
    cost_usd: float
    num_turns: int
    duration_ms: int
    commit_sha: str | None = None
    pr_url: str | None = None
    error_message: str | None = None
    stdout_tail: str = ""           # last 5000 chars of stdout
    stderr_tail: str = ""           # last 5000 chars of stderr
```

---

## What This Unlocks

Things that are impossible or painful with CI-based execution, and become straightforward with the agent runner:

| Capability | CI Today | Agent Runner |
|-----------|----------|--------------|
| **Use kimi-cli, qwen-code, swe-agent** | Impossible (no GitHub Actions) | Subprocess, works immediately |
| **A/B test engines on same task** | Requires workflow duplication | Runtime routing decision |
| **Fallback chains** | Crude (`continue-on-error` + second step) | `try engine A, catch, try engine B` in Python |
| **Cost-based routing** | Manual env var config | Orchestrator picks cheapest engine that meets quality threshold |
| **Persistent workspace** | Impossible (fresh checkout every run) | Keep workspace for triage -> write -> review loop |
| **Resume after timeout** | Impossible | Checkpoint and continue |
| **Local development** | Cannot test pipeline locally | `python -m apps.runner` with same adapters |
| **Custom compute** | 2 vCPU, 7 GB RAM | Whatever the runner runs on |
| **Real-time streaming** | No (batch output at end) | WebSocket or SSE from runner to orchestrator |

---

## Open Questions

1. **Git credentials in the runner.** CI gets `GITHUB_TOKEN` automatically. The runner needs a GitHub App installation token or a PAT. The orchestrator should mint short-lived tokens and pass them in the task request.

2. **Service containers.** CI spins up Postgres, Neo4j, Redis as service containers. The runner needs an equivalent. Options: Docker Compose sidecar, or connect to shared dev/staging databases.

3. **CLAUDE.md and rules injection.** Currently the agent reads CLAUDE.md from the repo checkout. This still works in the runner (it checks out the repo). But we could also inject rules via the task request for cross-repo agents.

4. **Concurrent task limits.** Cloud Run auto-scales, but each task may use significant memory. Need to set concurrency=1 per container instance and let Cloud Run handle scaling.

5. **Security isolation.** Engines execute arbitrary code (that is the whole point). Each task must run in an isolated environment. Cloud Run provides container isolation. For stronger guarantees, use gVisor or Firecracker.

---

## Next Steps

1. Build the `AgentEngine` protocol and `ClaudeCodeAdapter` as a standalone module in `apps/runner/engines/`
2. Build the runner HTTP service in `apps/runner/main.py`
3. Add workspace management (clone, branch, commit, push)
4. Wire orchestrator to optionally dispatch to runner instead of GitHub Actions
5. Deploy to Cloud Run, test with a real task
6. Add aider adapter (unlocks all LiteLLM models)
7. Add remaining adapters (kimi-cli, qwen-code, swe-agent)
