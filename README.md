# Automation Inventory REST API

A FastAPI service for managing hosts, automation agents and registered task definitions. The initial MVP implements the project brief's CRUD contract, validation, database migrations, optimistic concurrency, health checks and request logging.

Python 3.13 or newer is required. PostgreSQL 17 is the local container database. SQLite is available for a lightweight development run and isolated tests.

## Start with Docker Compose

1. Copy `.env.example` to `.env`.
2. Replace `POSTGRES_PASSWORD` with a unique local password using URL-safe letters and digits.
3. Run:

```sh
docker compose up --build --wait
```

The API starts only after PostgreSQL is healthy, applies Alembic migrations and serves at [http://localhost:8000](http://localhost:8000). Open [the API reference](http://localhost:8000/docs) for request and response schemas, or [readiness](http://localhost:8000/health/ready) to check database connectivity. Both exposed ports bind to the local loopback interface.

```sh
docker compose logs -f api
docker compose down
```

The named database volume retains data after `down`. Removing that volume deletes the local inventory; keep it for ordinary restarts. The example password is a placeholder for local development. Supply deployment credentials externally.

## Native development

Install Python 3.13+ and [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The default database is `sqlite+pysqlite:///./inventory.db`, relative to the current directory. Run commands from the repository root. Schema creation is managed by Alembic; starting the API alone does not create tables.

To use a separately running PostgreSQL instance, set `DATABASE_URL` before migrating and starting the application. For example, in PowerShell:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://inventory:YOUR_PASSWORD@localhost:5432/inventory'
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Percent-encode special characters in a database URL's username or password. Compose builds its URL from the `POSTGRES_*` settings in `.env`; a native process reads `DATABASE_URL` directly.

| Setting | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+pysqlite:///./inventory.db` | SQLAlchemy database URL; use the `postgresql+psycopg` driver for PostgreSQL. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. |
| `TEST_DATABASE_URL` | Unset | Optional isolated PostgreSQL database used by pytest; name must start with `inventory_test`. |
| `POSTGRES_USER` | `inventory` | Compose database user. |
| `POSTGRES_DB` | `inventory` | Compose database name. |
| `POSTGRES_PASSWORD` | Required by Compose | Database password supplied through local environment configuration. |
| `POSTGRES_PORT` | `5432` | Loopback host port for the Compose database. |

Application settings also read `.env`; shell environment values take precedence. Keep `.env` out of source control.

## API contract

All resource routes use the `/api/v1` prefix.

| Resource | Collection | Required creation fields | Filters |
| --- | --- | --- | --- |
| Hosts | `/hosts` | `hostname` | `status`, `environment` |
| Agents | `/agents` | `host_id`, `name` | `host_id`, `state` |
| Task definitions | `/tasks` | `name` | `agent_id`, `enabled` |

Every collection supports `POST` and `GET`. Each `/{id}` route supports `GET`, `PATCH` and `DELETE`. Creation returns HTTP 201, successful reads and updates return 200, and deletion returns 204 without a body. IDs are UUIDs. Every response resource has `version`, `created_at` and `updated_at`; timestamps use UTC.

Lists return:

```json
{"items": [], "total": 0, "limit": 20, "offset": 0}
```

The default `limit` is 20, the maximum is 100 and `offset` starts at 0. Results sort by `created_at` then `id` in ascending order, with the ID resolving timestamp ties. `total` counts matching records before pagination.

Host status is `active` (default), `inactive` or `maintenance`; environment defaults to `dev`. Hostnames are unique. Agent state is `offline` (default), `online` or `disabled`; an agent name is unique within its host. Optional `last_seen_at` must include a timezone. Task definitions may have a null `agent_id`, store a JSON object in `command_template_metadata` and default to `enabled: true`. JSON boolean fields require actual booleans.

Requests reject unknown properties, empty required names and invalid UUIDs or states with HTTP 422. References must point to existing resources. See generated OpenAPI documentation for full length limits and examples.

### Create and update

PowerShell example:

```powershell
$base = 'http://localhost:8000/api/v1'
$hostRecord = Invoke-RestMethod -Method Post -Uri "$base/hosts" -ContentType 'application/json' -Body '{"hostname":"worker-01","environment":"dev"}'
$agentRecord = Invoke-RestMethod -Method Post -Uri "$base/agents" -ContentType 'application/json' -Body (@{host_id=$hostRecord.id; name='runner-01'} | ConvertTo-Json)
$taskRecord = Invoke-RestMethod -Method Post -Uri "$base/tasks" -ContentType 'application/json' -Body (@{name='nightly-check'; agent_id=$agentRecord.id; command_template_metadata=@{template='inventory-check'; arguments=@()}} | ConvertTo-Json -Depth 5)
$hostRecord = Invoke-RestMethod -Method Patch -Uri "$base/hosts/$($hostRecord.id)" -ContentType 'application/json' -Body (@{version=$hostRecord.version; status='maintenance'} | ConvertTo-Json)
Invoke-RestMethod -Uri "$base/agents?host_id=$($hostRecord.id)&state=offline&limit=20&offset=0"
```

Task definitions are metadata. The API never runs templates or executes commands.

### Concurrency, deletion and errors

A `PATCH` body must include the version returned by the last read, for example `{"version":1,"status":"maintenance"}`. Successful updates increment the version. A stale version returns HTTP 409. Missing versions return 422. At least one editable property must be supplied.

Deletion requires `DELETE /api/v1/{resource}/{id}?version=N`, with the current version. Delete associated tasks first, then agents, then hosts. A referenced host or agent cannot be deleted and returns 409. An optional task association can be removed with `PATCH {"version":N,"agent_id":null}` before deleting its agent.

Missing resources return 404. Missing referenced parents return 422. Uniqueness, stale-write and referenced-parent deletion conflicts return 409. Database failures return 503. Resource API errors share this envelope:

```json
{
  "error": {
    "code": "example_code",
    "message": "A readable explanation",
    "details": null
  },
  "request_id": "correlation-id"
}
```

Every request returns an `X-Request-ID` header; valid supplied IDs are preserved. JSON request logs include this ID, request path, method, status and duration so errors can be correlated without logging request bodies.

## Storage and migrations

Writes run in explicit SQLAlchemy transactions. PostgreSQL uses its default `READ COMMITTED` isolation. Updates and deletes match both resource ID and version atomically; updates increment the version in the same statement. A concurrent stale writer affects no rows and receives a conflict. Database uniqueness, check constraints and foreign keys enforce integrity even when clients race.

There are indexes for each resource's `(created_at, id)` pagination order, the documented filter fields and foreign keys, plus unique hostname and `(host_id, name)` constraints. Filtered totals and results use separate queries; concurrent inserts or deletes may change totals between requests under `READ COMMITTED`. Offset pagination provides a deterministic order, without promising a frozen snapshot.

```sh
uv run alembic current
uv run alembic upgrade head
```

The initial migration is reversible with `uv run alembic downgrade base`. That command drops inventory tables and data; use it only on a disposable development or test database. CI rehearses upgrade, downgrade and upgrade against its isolated database. Back up persistent data before applying future production migrations. See [architecture decisions](docs/architecture.md).

## Verify changes

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
uv build
```

With no `TEST_DATABASE_URL`, tests migrate a temporary SQLite database and leave the application's local database alone. To verify PostgreSQL, create a disposable database whose name starts with `inventory_test`, set `TEST_DATABASE_URL`, then run pytest. Fixtures clear inventory rows in that test database between cases. Never supply a database containing valuable data.

GitHub Actions installs the lockfile, checks lint and formatting, rehearses migrations, runs the API suite with PostgreSQL 17, builds distributions, validates Compose, builds the locked container image, starts both services and smoke tests the running API. A configured check is not evidence that a hosted run has passed. Current local evidence and unverified items are recorded in [verification notes](docs/verification.md).

## Operations and troubleshooting

| Check or symptom | Action |
| --- | --- |
| `GET /health/live` | Process liveness; remains available without the database. |
| `GET /health` or `GET /health/ready` returns 200 | Database is reachable. A database failure returns 503 with `{"status":"not_ready"}`. |
| Startup reports missing tables | Run `uv run alembic upgrade head` using the same `DATABASE_URL` as the API. |
| Compose reports an unset password | Copy `.env.example` to `.env` and replace its placeholder. |
| Database credentials changed after first startup | PostgreSQL initializes credentials only on an empty volume. Update the existing database's credentials deliberately or use a new disposable volume. |
| Port 5432 or 8000 is already in use | Stop the conflicting local process or change the corresponding host-side Compose port. |
| PostgreSQL is unavailable | Inspect database health and API logs; restore connectivity, then retry readiness. |
| A stale update returns 409 | Fetch the latest version, reconcile changes and retry with that version. |

This learning MVP exposes no authentication, RBAC or tenant isolation. Use a trusted local network. Remote task execution, scheduling, Kubernetes and production deployment are outside its scope. Team ownership, external review and production security remain follow-up decisions from the brief.
