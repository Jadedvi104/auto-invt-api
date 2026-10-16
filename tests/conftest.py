"""Isolated database fixtures shared by the API acceptance tests."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import MetaData
from sqlalchemy.engine import make_url

from alembic import command
from app.config import Settings
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def database_environment(database_url: str):
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def database_url(tmp_path_factory):
    configured = os.environ.get("TEST_DATABASE_URL")
    if configured:
        parsed = make_url(configured)
        if parsed.get_backend_name() != "postgresql":
            raise pytest.UsageError("TEST_DATABASE_URL must refer to PostgreSQL.")
        if not parsed.database or not parsed.database.startswith("inventory_test"):
            raise pytest.UsageError(
                "TEST_DATABASE_URL database name must start with inventory_test; "
                "tests delete inventory rows in this isolated database."
            )
        url = configured
    else:
        path = tmp_path_factory.mktemp("inventory-db") / "inventory.db"
        url = f"sqlite+pysqlite:///{path.as_posix()}"
    with database_environment(url):
        command.upgrade(migration_config(url), "head")
    return url


def clear_inventory(engine):
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.begin() as connection:
        for table in reversed(metadata.sorted_tables):
            if table.name in {"hosts", "agents", "task_definitions", "tasks"}:
                connection.execute(table.delete())


@pytest.fixture
def app(database_url):
    application = create_app(Settings(database_url=database_url))
    clear_inventory(application.state.engine)
    yield application
    clear_inventory(application.state.engine)
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def host(client):
    response = client.post("/api/v1/hosts", json={"hostname": "worker-01"})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def agent(client, host):
    response = client.post("/api/v1/agents", json={"host_id": host["id"], "name": "runner-01"})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def task(client, agent):
    response = client.post(
        "/api/v1/tasks",
        json={
            "agent_id": agent["id"],
            "name": "nightly-check",
            "command_template_metadata": {"template": "inventory-check", "args": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
