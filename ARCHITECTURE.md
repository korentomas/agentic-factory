# Architecture

> **Template** — Customize this file for your codebase before deploying AgentFactory.
> Keep it under 60 lines. Every line is loaded into every agent's context window.
> Focus on invariants-as-absences: what is *never* allowed is as important as what is preferred.
> See: https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html

---

## Bird's Eye

<!-- 1–2 sentences describing what this system does and its key architectural constraints. -->

Multi-tenant SaaS platform. All data belongs to a tenant. External access via HTTP API. Internal graph via Neo4j. Primary relational store is Postgres.

---

## Codemap

<!-- Name files/modules explicitly. Don't hyperlink — links go stale, symbol search doesn't. -->

```
apps/api/app/
├── routers/          HTTP endpoints — thin, no business logic
├── services/         All business logic lives here
├── utils/
│   └── tenant_filter.py   Tenant isolation enforcement — THE critical file
├── neo4j_facade.py   Only interface to Neo4j — all Cypher lives here
├── auth/             Token validation — every router depends on this
└── schemas/          Pydantic models — the boundary types
apps/api/migrations/  Alembic Postgres migrations — never write raw DDL
apps/web/             Frontend — independent of API internal structure
```

---

## Architectural Invariants

**These are hard rules. Violations are BLOCKING in code review.**

- Routers do not touch the database directly. Business logic goes in `services/`.
- Nothing imports the Neo4j driver directly. All Cypher goes through `neo4j_facade`.
- No Neo4j write without a tenant label. `T_{tenant_id}` on every node and edge.
- Async routers never call sync functions. Check import source: `get_neo4j_facade` from `app.dependencies` is async; from `app.utils` is sync.
- No auth bypass. Every router except `/health` has `verify_token` or an equivalent dependency.
- No dynamic Cypher built from user input. Use parameterized queries only.
- No `DROP TABLE` outside of migrations.

---

## Layer Boundaries

```
HTTP Request
    │
    ▼
[routers/]  ← auth enforced here (verify_token dependency)
    │
    ▼
[services/] ← business logic, tenant scoping enforced here
    │         (tenant_filter.py must be called before any query)
    ├──▶ [Postgres via SQLAlchemy]
    └──▶ [neo4j_facade.py] ← all Cypher here, never raw driver
```

---

## Things That Change Frequently

- Route handlers in `routers/` — add freely following the existing pattern
- Service layer in `services/` — business logic evolves; always add tests
- Schema models — document breaking changes in the PR description

## Things That Almost Never Change

- `tenant_filter.py` — do not modify without a security review
- `neo4j_facade.py` interface — stable; add methods, never remove
- `auth/` — treat as read-only unless specifically tasked with auth work
