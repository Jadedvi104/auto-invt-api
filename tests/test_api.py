"""Public API contract: CRUD, relations, validation, lists, and lost-update prevention."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest

BASE = "/api/v1"


def assert_error(response, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert isinstance(body["error"]["code"], str)
    assert body["error"]["message"]
    assert body["request_id"] == response.headers["X-Request-ID"]
    return body


def test_host_crud_and_versioned_delete(client):
    response = client.post(f"{BASE}/hosts", json={"hostname": "worker-01", "environment": "dev"})
    assert response.status_code == 201, response.text
    host = response.json()
    UUID(host["id"])
    assert host["version"] == 1
    assert host["status"] == "active"
    assert host["created_at"]
    assert host["updated_at"]
    resource = f"{BASE}/hosts/{host['id']}"
    assert client.get(resource).json() == host
    updated = client.patch(resource, json={"version": 1, "status": "maintenance"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["status"] == "maintenance"
    assert updated.json()["created_at"] == host["created_at"]
    assert_error(client.delete(resource, params={"version": 1}), 409)
    deleted = client.delete(resource, params={"version": 2})
    assert deleted.status_code == 204
    assert not deleted.content
    assert_error(client.get(resource), 404)


def test_agent_and_task_crud(client, host):
    created = client.post(f"{BASE}/agents", json={"host_id": host["id"], "name": "runner"})
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["state"] == "offline"
    assert agent["last_seen_at"] is None
    agent_url = f"{BASE}/agents/{agent['id']}"
    changed = client.patch(
        agent_url,
        json={"version": 1, "state": "online", "last_seen_at": "2026-10-16T12:00:00Z"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 2
    assert changed.json()["state"] == "online"
    assert client.get(agent_url).json() == changed.json()

    created_task = client.post(
        f"{BASE}/tasks",
        json={
            "agent_id": agent["id"],
            "name": "collect-inventory",
            "command_template_metadata": {"template": "collect", "options": ["all"]},
        },
    )
    assert created_task.status_code == 201, created_task.text
    task = created_task.json()
    assert task["enabled"] is True
    task_url = f"{BASE}/tasks/{task['id']}"
    changed_task = client.patch(task_url, json={"version": 1, "enabled": False, "agent_id": None})
    assert changed_task.status_code == 200, changed_task.text
    assert changed_task.json()["version"] == 2
    assert changed_task.json()["agent_id"] is None
    assert changed_task.json()["enabled"] is False
    assert client.get(task_url).json() == changed_task.json()
    assert client.delete(task_url, params={"version": 2}).status_code == 204
    assert client.delete(agent_url, params={"version": 2}).status_code == 204


def test_unassigned_task_is_valid(client):
    response = client.post(f"{BASE}/tasks", json={"name": "unassigned"})
    assert response.status_code == 201, response.text
    assert response.json()["agent_id"] is None
    assert response.json()["command_template_metadata"] == {}


def test_duplicate_hostname_is_conflict_and_transaction_recovers(client, host):
    assert_error(client.post(f"{BASE}/hosts", json={"hostname": host["hostname"]}), 409)
    response = client.post(f"{BASE}/hosts", json={"hostname": "worker-02"})
    assert response.status_code == 201, response.text
    assert client.get(f"{BASE}/hosts").json()["total"] == 2


@pytest.mark.parametrize("resource,foreign_key", [("agents", "host_id"), ("tasks", "agent_id")])
def test_unknown_parent_is_clear_validation_error(client, resource, foreign_key):
    assert_error(
        client.post(f"{BASE}/{resource}", json={foreign_key: str(uuid4()), "name": "orphan"}),
        422,
    )
    assert client.get(f"{BASE}/{resource}").json()["total"] == 0


def test_referenced_deletes_are_rejected_then_cleanup_succeeds(client, host, agent, task):
    assert_error(client.delete(f"{BASE}/hosts/{host['id']}", params={"version": 1}), 409)
    assert_error(client.delete(f"{BASE}/agents/{agent['id']}", params={"version": 1}), 409)
    assert client.delete(f"{BASE}/tasks/{task['id']}", params={"version": 1}).status_code == 204
    assert client.delete(f"{BASE}/agents/{agent['id']}", params={"version": 1}).status_code == 204
    assert client.delete(f"{BASE}/hosts/{host['id']}", params={"version": 1}).status_code == 204


@pytest.mark.parametrize("resource", ["hosts", "agents", "tasks"])
def test_missing_resource_returns_404_for_read_update_and_delete(client, resource):
    url = f"{BASE}/{resource}/{uuid4()}"
    assert_error(client.get(url), 404)
    assert_error(
        client.patch(
            url,
            json={
                "version": 1,
                **({"hostname": "new"} if resource == "hosts" else {"name": "new"}),
            },
        ),
        404,
    )
    assert_error(client.delete(url, params={"version": 1}), 404)


@pytest.mark.parametrize(
    "resource,payload",
    [
        ("hosts", {"hostname": "   "}),
        ("hosts", {"hostname": "worker", "status": "unknown"}),
        ("hosts", {"hostname": "worker", "unexpected": True}),
        ("agents", {"host_id": "not-a-uuid", "name": "runner"}),
        ("tasks", {"name": "   "}),
        ("tasks", {"name": "task", "enabled": "false"}),
        ("tasks", {"name": "task", "enabled": 1}),
        ("tasks", {"name": "task", "command_template_metadata": []}),
    ],
)
def test_invalid_creation_is_422_without_mutation(client, resource, payload):
    assert_error(client.post(f"{BASE}/{resource}", json=payload), 422)
    assert client.get(f"{BASE}/{resource}").json()["total"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "inactive"},
        {"version": 0, "status": "inactive"},
        {"version": 1},
        {"version": 1, "hostname": None},
        {"version": 1, "status": None},
        {"version": 1, "unexpected": "value"},
    ],
)
def test_invalid_patch_does_not_change_resource(client, host, payload):
    url = f"{BASE}/hosts/{host['id']}"
    assert_error(client.patch(url, json=payload), 422)
    assert client.get(url).json() == host


@pytest.mark.parametrize("resource", ["hosts", "agents", "tasks"])
def test_invalid_path_id_is_validation_error(client, resource):
    assert_error(client.get(f"{BASE}/{resource}/invalid-uuid"), 422)


def test_delete_requires_version(client, host):
    assert_error(client.delete(f"{BASE}/hosts/{host['id']}"), 422)
    assert client.get(f"{BASE}/hosts/{host['id']}").status_code == 200


@pytest.mark.parametrize(
    "resource,fixture_name,field",
    [
        ("hosts", "host", "hostname"),
        ("agents", "agent", "name"),
        ("tasks", "task", "name"),
    ],
)
def test_stale_update_is_rejected_for_each_resource(client, request, resource, fixture_name, field):
    item = request.getfixturevalue(fixture_name)
    url = f"{BASE}/{resource}/{item['id']}"
    success = client.patch(url, json={"version": 1, field: "first-writer"})
    assert success.status_code == 200, success.text
    assert_error(client.patch(url, json={"version": 1, field: "stale-writer"}), 409)
    final = client.get(url).json()
    assert final["version"] == 2
    assert final[field] == "first-writer"


def test_parallel_updates_have_one_winner(client, host):
    url = f"{BASE}/hosts/{host['id']}"

    start = Barrier(2)

    def update(environment):
        start.wait(timeout=5)
        return client.patch(url, json={"version": 1, "environment": environment})

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(update, ["staging", "production"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert client.get(url).json()["environment"] == winner["environment"]
    assert client.get(url).json()["version"] == 2


def test_host_pagination_filters_totals_and_stability(client):
    for index in range(5):
        response = client.post(
            f"{BASE}/hosts",
            json={
                "hostname": f"host-{index}",
                "status": "active" if index < 4 else "inactive",
                "environment": "dev" if index < 3 else "prod",
            },
        )
        assert response.status_code == 201, response.text
    params = {"status": "active", "environment": "dev", "limit": 2}
    first = client.get(f"{BASE}/hosts", params=params).json()
    again = client.get(f"{BASE}/hosts", params=params).json()
    last = client.get(f"{BASE}/hosts", params={**params, "offset": 2}).json()
    assert first == again
    assert first["total"] == last["total"] == 3
    assert first["limit"] == 2
    assert first["offset"] == 0
    assert len(first["items"]) == 2
    assert len(last["items"]) == 1
    all_items = first["items"] + last["items"]
    assert len({item["id"] for item in all_items}) == 3
    keys = [(item["created_at"], item["id"]) for item in all_items]
    assert keys == sorted(keys)
    past_end = client.get(f"{BASE}/hosts", params={**params, "offset": 99}).json()
    assert past_end["items"] == []
    assert past_end["total"] == 3


def test_agent_and_task_filters(client, host, agent, task):
    second = client.post(f"{BASE}/hosts", json={"hostname": "other-host"}).json()
    client.post(
        f"{BASE}/agents", json={"host_id": second["id"], "name": "other", "state": "online"}
    )
    client.post(f"{BASE}/tasks", json={"name": "disabled", "enabled": False})
    agents = client.get(f"{BASE}/agents", params={"host_id": host["id"], "state": "offline"}).json()
    assert agents["total"] == 1
    assert agents["items"][0]["id"] == agent["id"]
    tasks = client.get(f"{BASE}/tasks", params={"agent_id": agent["id"], "enabled": True}).json()
    assert tasks["total"] == 1
    assert tasks["items"][0]["id"] == task["id"]
    assert client.get(f"{BASE}/tasks", params={"enabled": False}).json()["total"] == 1


@pytest.mark.parametrize("resource", ["hosts", "agents", "tasks"])
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_pagination_bounds(client, resource, params):
    assert_error(client.get(f"{BASE}/{resource}", params=params), 422)


def test_agent_names_are_unique_within_host_and_reassignment_is_versioned(client, host, agent):
    duplicate = client.post(f"{BASE}/agents", json={"host_id": host["id"], "name": agent["name"]})
    assert_error(duplicate, 409)
    second_host = client.post(f"{BASE}/hosts", json={"hostname": "worker-02"}).json()
    other = client.post(
        f"{BASE}/agents", json={"host_id": second_host["id"], "name": agent["name"]}
    )
    assert other.status_code == 201, other.text
    url = f"{BASE}/agents/{agent['id']}"
    conflict = client.patch(url, json={"version": 1, "host_id": second_host["id"]})
    assert_error(conflict, 409)
    assert client.get(url).json() == agent
    moved = client.patch(
        url, json={"version": 1, "host_id": second_host["id"], "name": "moved-runner"}
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["version"] == 2
    assert moved.json()["host_id"] == second_host["id"]


@pytest.mark.parametrize(
    "resource,fixture_name,field",
    [
        ("agents", "agent", "host_id"),
        ("tasks", "task", "agent_id"),
    ],
)
def test_invalid_reference_patch_does_not_mutate(client, request, resource, fixture_name, field):
    item = request.getfixturevalue(fixture_name)
    url = f"{BASE}/{resource}/{item['id']}"
    assert_error(client.patch(url, json={"version": 1, field: str(uuid4())}), 422)
    assert client.get(url).json() == item


def test_last_seen_requires_timezone_and_preserves_instant(client, agent):
    url = f"{BASE}/agents/{agent['id']}"
    assert_error(client.patch(url, json={"version": 1, "last_seen_at": "2026-10-16T19:00:00"}), 422)
    assert client.get(url).json() == agent
    updated = client.patch(url, json={"version": 1, "last_seen_at": "2026-10-16T19:00:00+07:00"})
    assert updated.status_code == 200, updated.text
    from datetime import datetime

    timestamp = datetime.fromisoformat(updated.json()["last_seen_at"])
    assert timestamp.isoformat() == "2026-10-16T12:00:00+00:00"
