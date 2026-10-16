# Initialization verification

The initialization checks below were run locally on 16 October 2026. Hosted CI and Docker Compose startup have separate status because local checks do not establish those results.

## Local results

| Check | Result |
| --- | --- |
| Runtime | Python 3.13.6; PostgreSQL 17.6. |
| API and operational tests, PostgreSQL | 52 passed in 13.22 seconds against an isolated local test database. |
| API and operational tests, SQLite | 52 passed in 3.63 seconds against temporary databases. |
| PostgreSQL migration rehearsal | Downgrade to base, upgrade to head and `alembic check` passed; no schema drift detected. |
| Ruff | Lint and formatting passed across 30 Python files. |
| Packaging | `uv build` produced the source distribution and wheel. |
| Clean wheel smoke test | Installed the wheel into an isolated virtual environment; applied source migrations; served real HTTP requests through uvicorn. Readiness, create/delete, OpenAPI examples and JSON request logs passed. |
| Compose configuration | `docker compose config` passed with disposable configuration. |

Docker Compose startup was **not verified locally**. Docker Desktop was started, but its engine returned HTTP 500. GitHub Actions is configured to build the locked image, start both services, wait for healthy status and exercise readiness, documentation and host creation.

Historical hosted validation of the identical implementation passed in the original combined repository at commit `30d1d7335d6687572ec608c72d2390851e740e88`: [Inventory API CI](https://github.com/Jadedvi104/asyn-web-data/actions/runs/38843929534) verified lint, formatting, PostgreSQL migrations and tests, package build, Compose startup, healthy services and live API smoke checks. That run used `inventory-api/` as its working directory.

The standalone `Jadedvi104/auto-invtory-rest` repository has the equivalent pipeline rooted at the repository directory. Per-commit results are available in [standalone repository Actions](https://github.com/Jadedvi104/auto-invtory-rest/actions). The historical run records implementation validation; use the standalone workflow for current repository status.

External reviewer demo and sign-off: pending.

## Acceptance coverage

| Brief test | Evidence |
| --- | --- |
| INV-01 host CRUD | API tests cover create, list, read, versioned update and delete; clean wheel smoke uses real HTTP create/delete. |
| INV-02 unknown parent | API tests reject missing host and agent references. |
| INV-03 filtered pagination | API tests cover filters, totals, bounded pages and stable ordering. |
| INV-04 stale updates | Tests cover stale writes and a concurrent update race with one winning version. |
| INV-05 clean migration | Tests create isolated schemas through Alembic; clean wheel smoke uses migrated storage. |
| INV-06 rollback | PostgreSQL downgrade/upgrade rehearsal and schema drift check passed; temporary SQLite rollback also covered. |
| INV-07 unavailable database | Tests simulate storage failure and verify readiness failure, liveness availability and request error behavior. |
| INV-08 invalid payload | Tests cover 422 responses and unchanged stored state. |
| INV-09 Compose startup | Passed in the historical hosted Inventory API CI for the identical implementation; the standalone workflow repeats the container health and API smoke checks. |

Commands below run from the root of the standalone `auto-invtory-rest` repository.

## Reproduction

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
uv build
docker compose config --quiet
docker compose up --build --wait
```

Supply a unique local `POSTGRES_PASSWORD` for Compose. For PostgreSQL tests, set `TEST_DATABASE_URL` to a disposable database named `inventory_test...` and repeat pytest. To rehearse migrations explicitly, set `DATABASE_URL` to that disposable database, then run:

```sh
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
```

The downgrade drops inventory data. Tests clear inventory rows in their configured test database.
