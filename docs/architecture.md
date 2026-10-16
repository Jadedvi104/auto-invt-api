# Architecture and contract decisions

The brief is the implementation baseline. These decisions freeze its illustrative choices for this initial release.

| Area | Decision and reason |
| --- | --- |
| Runtime | Python 3.13+, FastAPI and Pydantic 2; uv lockfile for native development, CI and the container image. |
| Storage | PostgreSQL 17 for integration and Compose. SQLite is a development convenience; PostgreSQL remains the acceptance target. |
| API version | `/api/v1`; task definitions use the collection name `tasks`. |
| Concurrency | Mandatory integer body `version` for PATCH and query `version` for DELETE. Atomic conditional statements return 409 for stale writes. Every resource includes version and both timestamps. |
| Relationships | Agent requires a host. Task optionally references an agent. Foreign keys restrict parent deletion so inventory associations cannot disappear implicitly. |
| Names | Unique hostnames and unique agent names per host. Task names are descriptive and need not be unique. |
| Validation | Pydantic validates input, rejects unknown properties and requires timezone-aware user timestamps. Database checks provide an additional integrity boundary. |
| Lists | Bounded offset pagination, total matching count, stable ascending `created_at, id` order. Concurrent writes may shift later pages and counts. |
| Errors | Shared error envelope, correlation ID and documented 404/409/422/503 statuses. |
| Configuration | Environment-backed settings and ignored local `.env`; no production credentials tracked in source. |
| Startup | Migrations run explicitly for native development and before the Compose API server. No application `create_all` shortcut. |
| Health | `/health/live` checks liveness; `/health` and `/health/ready` check database connectivity. |
| Logging | Structured request logs and `X-Request-ID`; request bodies are omitted. |
| Tests | Migrated temporary SQLite by default; explicitly named disposable PostgreSQL databases via `TEST_DATABASE_URL`. |
| Delivery | Packaged `app`, Alembic source in repository and container, non-root container user, loopback local port bindings. |

## Component boundaries

`app/api/v1` defines routes and dependencies. Pydantic schemas define the public contract. The service layer implements relationship checks and converts storage conflicts into API errors. Repositories issue ORM queries and atomic writes. `app/db` defines SQLAlchemy models and engine/session setup; Alembic owns schema changes.

Each request uses a session and each write has an explicit transaction boundary. SQLAlchemy binds user values as parameters. PostgreSQL `READ COMMITTED` is sufficient for version-checked updates because the ID and expected version participate in the modifying statement itself. The database checks foreign keys and unique constraints inside that transaction.

Stable sort indexes exist for all collections. Separate indexes support host status/environment, agent state/host, task enabled/agent and uniqueness constraints. These are baseline indexes for the documented filters; additional composite indexes should follow measured workload rather than assumed production traffic.

## Scope and rollback

The initial migration creates all inventory tables and indexes. Its downgrade removes them in dependency order. This is a destructive rollback suitable for disposable rehearsal databases; persistent deployments need backups and an explicit recovery plan before downgrade.

Task metadata never triggers execution. Authentication, RBAC, multiple tenants, distributed scheduling and production hosting are deferred by the brief. This initialization does not establish production readiness or reviewer sign-off.
