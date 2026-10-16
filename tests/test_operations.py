"""Migration and operational acceptance checks on disposable databases."""

import json
import logging

from conftest import database_environment, migration_config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError

from alembic import command
from app.config import Settings
from app.main import create_app


def test_migrations_upgrade_downgrade_and_reupgrade(tmp_path):
    path = tmp_path / "migration-rehearsal.db"
    database_url = f"sqlite+pysqlite:///{path.as_posix()}"
    config = migration_config(database_url)
    with database_environment(database_url):
        command.upgrade(config, "head")
        engine = create_engine(database_url)
        tables = set(inspect(engine).get_table_names())
        assert {"hosts", "agents", "task_definitions"} <= tables
        engine.dispose()
        command.downgrade(config, "base")
        engine = create_engine(database_url)
        assert not (
            {"hosts", "agents", "task_definitions"} & set(inspect(engine).get_table_names())
        )
        engine.dispose()
        command.upgrade(config, "head")
    application = create_app(Settings(database_url=database_url))
    with TestClient(application) as client:
        assert client.get("/health/ready").status_code == 200
        response = client.post("/api/v1/hosts", json={"hostname": "migrated-host"})
        assert response.status_code == 201, response.text
    application.state.engine.dispose()


def test_health_endpoints_and_openapi(client):
    for path in ("/health", "/health/live", "/health/ready"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert response.json()["status"]
    schema = client.get("/openapi.json").json()
    for resource in ("hosts", "agents", "tasks"):
        assert f"/api/v1/{resource}" in schema["paths"]
        assert f"/api/v1/{resource}/{{resource_id}}" in schema["paths"] or any(
            path.startswith(f"/api/v1/{resource}/{{") for path in schema["paths"]
        )


def test_readiness_failure_does_not_break_liveness(client, app, monkeypatch, caplog):
    def unavailable(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(app.state.engine, "connect", unavailable)
    with caplog.at_level(logging.ERROR, logger="inventory.health"):
        response = client.get("/health/ready")
    assert response.status_code == 503, response.text
    assert response.json()["status"]
    assert client.get("/health/live").status_code == 200
    assert any(record.name == "inventory.health" for record in caplog.records)


def test_request_ids_are_echoed_generated_and_attached_to_errors(client):
    supplied = "acceptance-request-123"
    response = client.get("/health/live", headers={"X-Request-ID": supplied})
    assert response.headers["X-Request-ID"] == supplied
    generated = client.get("/health/live").headers["X-Request-ID"]
    assert generated
    assert generated != supplied
    invalid = client.get("/health/live", headers={"X-Request-ID": "unsafe request id"})
    assert invalid.headers["X-Request-ID"] != "unsafe request id"
    error = client.get("/api/v1/hosts/not-a-uuid", headers={"X-Request-ID": supplied})
    assert error.status_code == 422
    assert error.json()["request_id"] == supplied


def test_requests_emit_structured_json_log(client, caplog):
    with caplog.at_level(logging.INFO, logger="inventory.requests"):
        response = client.get("/health/live", headers={"X-Request-ID": "logging-test"})
    assert response.status_code == 200
    records = [record for record in caplog.records if record.name == "inventory.requests"]
    assert records
    payload = json.loads(records[-1].getMessage())
    assert payload["request_id"] == "logging-test"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health/live"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] >= 0
