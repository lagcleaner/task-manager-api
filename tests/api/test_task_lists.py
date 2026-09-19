from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserModel, UserRole

_PASSWORD = "correct-horse-1"


async def _register_and_login(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/v1/auth/register", json={"email": email, "password": _PASSWORD})
    response = await client.post("/v1/auth/login", json={"email": email, "password": _PASSWORD})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_task_list(client: AsyncClient, headers: dict[str, str], name: str) -> int:
    response = await client.post("/v1/task-lists", json={"name": name}, headers=headers)
    list_id: int = response.json()["id"]
    return list_id


async def _create_task(
    client: AsyncClient,
    headers: dict[str, str],
    list_id: int,
    title: str,
    *,
    priority: str | None = None,
) -> int:
    payload: dict[str, object] = {"title": title, "list_id": list_id}
    if priority is not None:
        payload["priority"] = priority
    response = await client.post("/v1/tasks", json=payload, headers=headers)
    task_id: int = response.json()["id"]
    return task_id


async def test_create_task_list_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/v1/task-lists", json={"name": "Groceries"})

    assert response.status_code == 401


async def test_create_task_list_returns_201(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "creator@example.com")

    response = await client.post("/v1/task-lists", json={"name": "Groceries"}, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Groceries"
    assert body["owner_id"] is not None


async def test_get_task_list_returns_404_when_missing(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "reader@example.com")

    response = await client.get("/v1/task-lists/999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_list_not_found"


async def test_list_task_lists_returns_created_lists(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "lister@example.com")
    await client.post("/v1/task-lists", json={"name": "First"}, headers=headers)
    await client.post("/v1/task-lists", json={"name": "Second"}, headers=headers)

    response = await client.get("/v1/task-lists", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_update_task_list_changes_name(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "updater@example.com")
    created = await client.post("/v1/task-lists", json={"name": "Old name"}, headers=headers)
    list_id = created.json()["id"]

    response = await client.patch(
        f"/v1/task-lists/{list_id}", json={"name": "New name"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New name"


async def test_delete_task_list_as_regular_user_returns_403(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "regular@example.com")
    created = await client.post("/v1/task-lists", json={"name": "Temp"}, headers=headers)
    list_id = created.json()["id"]

    response = await client.delete(f"/v1/task-lists/{list_id}", headers=headers)

    assert response.status_code == 403


async def test_delete_task_list_as_admin_returns_204(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "admin@example.com"
    headers = await _register_and_login(client, email)
    created = await client.post("/v1/task-lists", json={"name": "Temp"}, headers=headers)
    list_id = created.json()["id"]

    # Registration never grants admin; promote directly in the store, the way
    # a real deployment would via an internal tool, not a self-service endpoint.
    result = await db_session.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one()
    user.role = UserRole.ADMIN
    await db_session.commit()

    response = await client.delete(f"/v1/task-lists/{list_id}", headers=headers)

    assert response.status_code == 204


async def test_list_tasks_for_task_list_scopes_to_that_list_only(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "scoped@example.com")
    list_a = await _create_task_list(client, headers, "List A")
    list_b = await _create_task_list(client, headers, "List B")
    await _create_task(client, headers, list_a, "A1")
    await _create_task(client, headers, list_a, "A2")
    await _create_task(client, headers, list_b, "B1")

    response = await client.get(f"/v1/task-lists/{list_a}/tasks", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert {task["title"] for task in body["tasks"]} == {"A1", "A2"}
    assert all(task["list_id"] == list_a for task in body["tasks"])


async def test_list_tasks_for_task_list_filters_by_status(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "status-filter@example.com")
    list_id = await _create_task_list(client, headers, "Filtered")
    pending_id = await _create_task(client, headers, list_id, "Pending task")
    done_id = await _create_task(client, headers, list_id, "Done task")
    await client.patch(f"/v1/tasks/{done_id}/status", json={"status": "completed"}, headers=headers)

    response = await client.get(
        f"/v1/task-lists/{list_id}/tasks", params={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert [task["id"] for task in body["tasks"]] == [done_id]
    assert pending_id not in [task["id"] for task in body["tasks"]]


async def test_list_tasks_for_task_list_filters_by_priority(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "priority-filter@example.com")
    list_id = await _create_task_list(client, headers, "Filtered")
    high_id = await _create_task(client, headers, list_id, "Urgent", priority="high")
    await _create_task(client, headers, list_id, "Whenever", priority="low")

    response = await client.get(
        f"/v1/task-lists/{list_id}/tasks", params={"priority": "high"}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert [task["id"] for task in body["tasks"]] == [high_id]


async def test_list_tasks_for_task_list_computes_completion_percentage(
    client: AsyncClient,
) -> None:
    headers = await _register_and_login(client, "percentage@example.com")
    list_id = await _create_task_list(client, headers, "Percentages")
    completed_id = await _create_task(client, headers, list_id, "One")
    await _create_task(client, headers, list_id, "Two")
    await _create_task(client, headers, list_id, "Three")
    await _create_task(client, headers, list_id, "Four")
    await client.patch(
        f"/v1/tasks/{completed_id}/status", json={"status": "completed"}, headers=headers
    )

    response = await client.get(f"/v1/task-lists/{list_id}/tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()["completion_percentage"] == 25.0


async def test_list_tasks_for_task_list_completion_percentage_is_unaffected_by_filters(
    client: AsyncClient,
) -> None:
    headers = await _register_and_login(client, "percentage-filtered@example.com")
    list_id = await _create_task_list(client, headers, "Percentages filtered")
    completed_id = await _create_task(client, headers, list_id, "One")
    await _create_task(client, headers, list_id, "Two")
    await _create_task(client, headers, list_id, "Three")
    await _create_task(client, headers, list_id, "Four")
    await client.patch(
        f"/v1/tasks/{completed_id}/status", json={"status": "completed"}, headers=headers
    )

    response = await client.get(
        f"/v1/task-lists/{list_id}/tasks", params={"status": "pending"}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["tasks"]) == 3
    assert body["completion_percentage"] == 25.0


async def test_list_tasks_for_task_list_returns_zero_percentage_when_empty(
    client: AsyncClient,
) -> None:
    headers = await _register_and_login(client, "empty-list@example.com")
    list_id = await _create_task_list(client, headers, "Empty")

    response = await client.get(f"/v1/task-lists/{list_id}/tasks", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["tasks"] == []
    assert body["completion_percentage"] == 0.0


async def test_list_tasks_for_task_list_returns_404_when_list_missing(
    client: AsyncClient,
) -> None:
    headers = await _register_and_login(client, "missing-list@example.com")

    response = await client.get("/v1/task-lists/999/tasks", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_list_not_found"


async def test_invite_to_task_list_requires_authentication(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "inviter-noauth@example.com")
    list_id = await _create_task_list(client, headers, "Invitable")

    response = await client.post(
        f"/v1/task-lists/{list_id}/invitations", json={"email": "invitee@example.com"}
    )

    assert response.status_code == 401


async def test_invite_to_task_list_returns_201(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "inviter@example.com")
    list_id = await _create_task_list(client, headers, "Invitable")

    response = await client.post(
        f"/v1/task-lists/{list_id}/invitations",
        json={"email": "invitee@example.com"},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["list_id"] == list_id
    assert body["email"] == "invitee@example.com"
    assert body["invited_by_id"] is not None
    assert body["id"] is not None


async def test_invite_to_task_list_returns_404_when_list_missing(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "inviter-missing@example.com")

    response = await client.post(
        "/v1/task-lists/999/invitations", json={"email": "invitee@example.com"}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_list_not_found"


async def test_invite_to_task_list_returns_409_when_duplicate(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "inviter-dup@example.com")
    list_id = await _create_task_list(client, headers, "Invitable")
    await client.post(
        f"/v1/task-lists/{list_id}/invitations",
        json={"email": "invitee@example.com"},
        headers=headers,
    )

    response = await client.post(
        f"/v1/task-lists/{list_id}/invitations",
        json={"email": "invitee@example.com"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "duplicate_invitation"


async def test_list_invitations_for_task_list_returns_created_invitations(
    client: AsyncClient,
) -> None:
    headers = await _register_and_login(client, "invitation-lister@example.com")
    list_id = await _create_task_list(client, headers, "Invitable")
    await client.post(
        f"/v1/task-lists/{list_id}/invitations",
        json={"email": "one@example.com"},
        headers=headers,
    )
    await client.post(
        f"/v1/task-lists/{list_id}/invitations",
        json={"email": "two@example.com"},
        headers=headers,
    )

    response = await client.get(f"/v1/task-lists/{list_id}/invitations", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert {invitation["email"] for invitation in body} == {"one@example.com", "two@example.com"}
    assert all(invitation["list_id"] == list_id for invitation in body)


async def test_list_invitations_for_task_list_returns_404_when_list_missing(
    client: AsyncClient,
) -> None:
    headers = await _register_and_login(client, "invitation-lister-missing@example.com")

    response = await client.get("/v1/task-lists/999/invitations", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_list_not_found"


async def test_list_invitations_for_task_list_requires_authentication(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "invitation-lister-noauth@example.com")
    list_id = await _create_task_list(client, headers, "Invitable")

    response = await client.get(f"/v1/task-lists/{list_id}/invitations")

    assert response.status_code == 401
