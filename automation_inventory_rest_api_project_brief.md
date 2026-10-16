# Automation Inventory REST API — Project Brief

**Project ID:** P06
**Status:** Proposed MVP / Ready for team kickoff
**Audience:** Engineering, QA, DevOps and project reviewers
**Suggested delivery:** Weeks 9–10 (50h); confirm capacity with the team
**Primary language:** Python 3.13+ (or a currently supported Python 3.x version)
**Document type:** Engineering brief / implementation contract

## 1. Executive Summary

A containerized FastAPI application that tracks managed hosts, automation agents and registered task definitions. It exposes versioned REST APIs and transactional PostgreSQL persistence to support reliable inventory operations.

## 2. Goals and Success Metrics

**Goals**

- Model assets, agent ownership, state and task-to-agent associations.
- Expose consistent CRUD, filtering, pagination, validation and clear error semantics.
- Deliver reproducible database migrations, integration tests and local container orchestration.

**MVP success**

- API resources can be created, read, updated, listed and deleted through documented endpoints.
- Concurrent updates follow a defined lost-update prevention mechanism.
- A clean checkout starts the API and PostgreSQL via Docker Compose and passes tests.

## 3. Users and Use Cases

- DevOps team tracking automation hosts/agents
- Developers building integration clients
- QA team validating persistence and contract changes

## 4. MVP Scope

### In Scope

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-01 | CRUD endpoints for hosts, agents and task definitions | Must |
| FR-02 | Explicit relations: agents belong to a host; tasks may target an agent | Must |
| FR-03 | Pydantic request/response schemas with meaningful validation errors | Must |
| FR-04 | Pagination, filter by status/host and stable sort order | Must |
| FR-05 | SQLAlchemy transaction boundaries and Alembic migrations | Must |
| FR-06 | Health, liveness and readiness endpoints | Must |
| FR-07 | Optimistic concurrency using version field or conditional update | Must |
| FR-08 | OpenAPI documentation and examples | Must |
| FR-09 | Structured request logs and correlation/request IDs | Should |
| FR-10 | Containerized local environment and automated CI integration tests | Must |

### Explicitly Out of Scope

- Executing automation tasks remotely or accepting arbitrary executable payloads.
- Production authentication/RBAC and multi-tenant isolation (explicit later projects).
- Kubernetes deployment, distributed scheduling and event streaming.

## 5. User Interface / API Contract

```bash
# Start local PostgreSQL + API
docker compose up --build
# Create a host
curl -X POST http://localhost:8000/api/v1/hosts -H "Content-Type: application/json" -d '{"hostname":"worker-01","environment":"dev"}'
# Inspect health and API contract
curl http://localhost:8000/health/ready
# Browse generated OpenAPI reference
# http://localhost:8000/docs
# Run migrations and tests
uv run alembic upgrade head
uv run pytest -v
```

**Contract guidelines:** CLI arguments and output formats are illustrative starting points. Freeze names, exit codes, and schemas during kickoff; document changes and make acceptance tests authoritative.

## 6. Technical Specification

### Proposed Stack

Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Docker Compose, pytest

### Domain / Data Contract

```text
Suggested PostgreSQL tables:
hosts(id UUID PK, hostname UNIQUE, environment, status, version INT, created_at, updated_at)
agents(id UUID PK, host_id FK, name, state, last_seen_at, version INT, created_at)
task_definitions(id UUID PK, agent_id FK NULL, name, command_template_metadata, enabled, created_at, updated_at)

Version increments on updates; reject stale If-Match/version values with 409 or 412 according to API contract. Task commands are metadata only in this release.
```

### System Components

- API routes (FastAPI): versioned request/response contracts, dependency injection.
- Schemas: Pydantic validation and serialization, error response envelope.
- Service layer: host/agent/task business rules and version checks.
- Repository layer: SQLAlchemy operations with explicit transactions.
- PostgreSQL/Alembic: constraints and schema migration lifecycle.
- Operational layer: Docker Compose, startup readiness and JSON structured logging.

### Suggested Repository Structure

```text
project-root/
├── app/main.py
├── app/api/v1/hosts.py
├── app/api/v1/agents.py
├── app/api/v1/tasks.py
├── app/schemas/
├── app/services/
├── app/repositories/
├── app/db/models.py
├── app/db/session.py
├── alembic/
├── tests/unit/
├── tests/integration/
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── README.md
```

## 7. Non-Functional Requirements and Safeguards

- Use bound SQL parameters/ORM; never interpolate user input into raw SQL.
- Restrict database access to local/test networks for this learning MVP.
- Avoid hard-coded credentials; use environment configuration and example env file.
- Use deterministic sorting and bounded pagination with documented maximum limit.
- Document transaction/isolation assumptions and database index choices.

## 8. Implementation Plan

| Sprint/day | Engineering work |
| --- | --- |
| Week 9 — Days 1–2 | Domain model, endpoints, repo skeleton, Compose and initial migrations. |
| Week 9 — Days 3–5 | Host/agent CRUD, task definitions, validation, constraints and services. |
| Week 10 — Days 1–2 | Pagination, filtering, optimistic locking and transactions. |
| Week 10 — Days 3–4 | Unit/integration tests, logs, readiness, CI and OpenAPI examples. |
| Week 10 — Day 5 | Fresh-environment deployment, migration rehearsal, contract demo. |

**Recommended cadence:** kickoff/design → first vertical slice → negative-path tests → packaging/CI → demo and review. Keep PRs small and reviewable.

## 9. Acceptance Tests

| Test ID | Scenario | Expected result |
| --- | --- | --- |
| INV-01 | Create/read/update/delete host | REST status and body match documented contracts. |
| INV-02 | Create agent for unknown host | Foreign key/domain validation rejects with clear error. |
| INV-03 | List agents with filter + pagination | Stable ordering, page bounds and totals as documented. |
| INV-04 | Two clients update same version | One update succeeds; stale request gets conflict. |
| INV-05 | Apply migrations to empty DB | Resulting schema supports application start. |
| INV-06 | Migration rollback rehearsal | Downgrade policy tested or explicit irreversible step documented. |
| INV-07 | Database unavailable | Readiness returns non-ready; failures are observable. |
| INV-08 | Invalid payload | Returns HTTP 422 (or documented validation status) without DB mutation. |
| INV-09 | Docker Compose startup | API and DB become healthy; integration suite passes. |

**Testing approach:** pytest unit tests and integration tests with fixture files/services. Include negative paths, deterministic behavior, and a clean-install smoke test. Use isolated temporary directories/databases; never run destructive tests on real user or production data.

## 10. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Lost updates under concurrency | Version field, conditional update and conflict tests. |
| Schema drift | Alembic migrations versioned and exercised in CI. |
| Secrets in source control | Example env file, gitignore, external configuration. |
| Unbounded list queries | Maximum page size, stable indexing, filtered queries. |

## 11. Team Workstreams and Deliverables

| Workstream | Suggested owner | Evidence / deliverable |
| --- | --- | --- |
| Specification and data contract | Tech lead / developer | Reviewed README, assumptions, diagrams, CLI/API examples |
| Implementation and integration | Python developer(s) | Working packaged application, sample configuration |
| Verification | Developer + QA | Automated unit/integration tests and acceptance report |
| Delivery and reliability | DevOps / maintainer | Reproducible setup, CI, operational notes |

**Ownership note:** Assign actual people and sprint dates at kickoff. These are roles, not staffing assumptions.

## 12. Definition of Done

- [ ] Functional MVP scope is delivered or explicitly descoped with approval.
- [ ] Acceptance tests in §9 pass on a clean environment.
- [ ] README includes install, configuration, usage, limitations and troubleshooting.
- [ ] Automated tests cover success, invalid input, and failure-recovery paths.
- [ ] Ruff checks, packaging/build and GitHub Actions CI pass.
- [ ] No credentials, private datasets or machine-specific absolute paths are committed.
- [ ] Operational metrics/benchmarks are attached where required.
- [ ] Reviewer has run the principal end-to-end demo and signed off.

## 13. References

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [PostgreSQL](https://www.postgresql.org/docs/)
- [Docker Compose](https://docs.docker.com/compose/)

## 14. Open Decisions for Kickoff

- Confirm team owner, reviewers and delivery dates.
- Confirm Python runtime and support platforms (Windows/macOS/Linux) as applicable.
- Freeze default configuration, naming, CLI/API behavior and error formats.
- Agree test evidence, operational limits and rollback/recovery expectations.

---
*Prepared for engineering kickoff. This document is a proposed baseline, not evidence of implementation or completed tests.*
