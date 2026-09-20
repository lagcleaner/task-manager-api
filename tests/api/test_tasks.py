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
    client: AsyncClient, headers: dict[str, str], list_id: int, title: str
) -> int:
    response = await client.post(
        "/v1/tasks", json={"title": title, "list_id": list_id}, headers=headers
    )
    task_id: int = response.json()["id"]
    return task_id


async def test_create_task_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/v1/tasks", json={"title": "Write tests", "list_id": 1})

    assert response.status_code == 401


async def test_create_task_returns_201(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "creator@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")

    response = await client.post(
        "/v1/tasks", json={"title": "Write tests", "list_id": list_id}, headers=headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Write tests"
    assert body["status"] == "pending"
    assert body["priority"] == "medium"
    assert body["list_id"] == list_id


async def test_create_task_returns_404_when_list_missing(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "orphan@example.com")

    response = await client.post(
        "/v1/tasks", json={"title": "Write tests", "list_id": 999}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_list_not_found"


async def test_get_task_returns_404_when_missing(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "reader@example.com")

    response = await client.get("/v1/tasks/999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


async def test_list_tasks_returns_created_tasks(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "lister@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    await client.post("/v1/tasks", json={"title": "First", "list_id": list_id}, headers=headers)
    await client.post("/v1/tasks", json={"title": "Second", "list_id": list_id}, headers=headers)

    response = await client.get("/v1/tasks", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_update_task_changes_status(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "updater@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    created = await client.post(
        "/v1/tasks", json={"title": "Ship feature", "list_id": list_id}, headers=headers
    )
    task_id = created.json()["id"]

    response = await client.patch(
        f"/v1/tasks/{task_id}", json={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


async def test_change_task_status_returns_200(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "status-updater@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    created = await client.post(
        "/v1/tasks", json={"title": "Ship feature", "list_id": list_id}, headers=headers
    )
    task_id = created.json()["id"]

    response = await client.patch(
        f"/v1/tasks/{task_id}/status", json={"status": "in_progress"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


async def test_change_task_status_returns_404_when_missing(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "status-missing@example.com")

    response = await client.patch(
        "/v1/tasks/999/status", json={"status": "in_progress"}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


async def test_assign_task_returns_200(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "assigner@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    created = await client.post(
        "/v1/tasks", json={"title": "Ship feature", "list_id": list_id}, headers=headers
    )
    task_id = created.json()["id"]
    result = await client.post(
        "/v1/auth/register", json={"email": "assignee@example.com", "password": _PASSWORD}
    )
    assignee_id = result.json()["id"]

    response = await client.patch(
        f"/v1/tasks/{task_id}/assignee", json={"assignee_id": assignee_id}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["assignee_id"] == assignee_id


async def test_assign_task_returns_404_when_task_missing(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "assigner-missing-task@example.com")

    response = await client.patch(
        "/v1/tasks/999/assignee", json={"assignee_id": None}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


async def test_assign_task_returns_404_when_user_missing(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "assigner-missing-user@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    created = await client.post(
        "/v1/tasks", json={"title": "Ship feature", "list_id": list_id}, headers=headers
    )
    task_id = created.json()["id"]

    response = await client.patch(
        f"/v1/tasks/{task_id}/assignee", json={"assignee_id": 999}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "user_not_found"


async def test_assign_task_requires_authentication(client: AsyncClient) -> None:
    response = await client.patch("/v1/tasks/1/assignee", json={"assignee_id": None})

    assert response.status_code == 401


async def _promote_to_admin(db_session: AsyncSession, email: str) -> None:
    # Registration never grants admin; promote directly in the store, the way
    # a real deployment would via an internal tool, not a self-service endpoint.
    result = await db_session.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one()
    user.role = UserRole.ADMIN
    await db_session.commit()


async def test_delete_task_as_owner_returns_204(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "owner@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    task_id = await _create_task(client, headers, list_id, "Temp")

    response = await client.delete(f"/v1/tasks/{task_id}", headers=headers)

    assert response.status_code == 204
    get_response = await client.get(f"/v1/tasks/{task_id}", headers=headers)
    assert get_response.status_code == 404


async def test_delete_task_as_regular_user_returns_403(client: AsyncClient) -> None:
    owner_headers = await _register_and_login(client, "owner2@example.com")
    list_id = await _create_task_list(client, owner_headers, "Groceries")
    task_id = await _create_task(client, owner_headers, list_id, "Temp")
    other_headers = await _register_and_login(client, "regular@example.com")

    response = await client.delete(f"/v1/tasks/{task_id}", headers=other_headers)

    assert response.status_code == 403


async def test_delete_task_as_assignee_non_owner_returns_403(client: AsyncClient) -> None:
    owner_headers = await _register_and_login(client, "owner3@example.com")
    list_id = await _create_task_list(client, owner_headers, "Groceries")
    task_id = await _create_task(client, owner_headers, list_id, "Temp")
    registered = await client.post(
        "/v1/auth/register", json={"email": "assignee@example.com", "password": _PASSWORD}
    )
    assignee_id = registered.json()["id"]
    await client.patch(
        f"/v1/tasks/{task_id}/assignee", json={"assignee_id": assignee_id}, headers=owner_headers
    )
    login = await client.post(
        "/v1/auth/login", json={"email": "assignee@example.com", "password": _PASSWORD}
    )
    assignee_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Being the assignee doesn't grant delete rights — only the owning list's owner has them.
    response = await client.delete(f"/v1/tasks/{task_id}", headers=assignee_headers)

    assert response.status_code == 403


async def test_delete_task_requires_authentication(client: AsyncClient) -> None:
    response = await client.delete("/v1/tasks/1")

    assert response.status_code == 401


async def test_delete_task_as_admin_non_owner_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner_headers = await _register_and_login(client, "owner6@example.com")
    list_id = await _create_task_list(client, owner_headers, "Groceries")
    task_id = await _create_task(client, owner_headers, list_id, "Temp")
    admin_email = "admin-nonowner@example.com"
    admin_headers = await _register_and_login(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    # The regular (non-permanent) DELETE route is ownership-gated even for admins —
    # only /permanent bypasses ownership. Admin role must not implicitly grant it.
    response = await client.delete(f"/v1/tasks/{task_id}", headers=admin_headers)

    assert response.status_code == 403


async def test_permanent_delete_task_as_admin_returns_204(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "admin@example.com"
    headers = await _register_and_login(client, email)
    list_id = await _create_task_list(client, headers, "Groceries")
    task_id = await _create_task(client, headers, list_id, "Temp")
    await _promote_to_admin(db_session, email)

    response = await client.delete(f"/v1/tasks/{task_id}/permanent", headers=headers)

    assert response.status_code == 204


async def test_permanent_delete_task_as_admin_works_on_already_soft_deleted_task(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "admin2@example.com"
    headers = await _register_and_login(client, email)
    list_id = await _create_task_list(client, headers, "Groceries")
    task_id = await _create_task(client, headers, list_id, "Temp")
    await client.delete(f"/v1/tasks/{task_id}", headers=headers)
    await _promote_to_admin(db_session, email)

    response = await client.delete(f"/v1/tasks/{task_id}/permanent", headers=headers)

    assert response.status_code == 204


async def test_permanent_delete_task_as_non_admin_returns_403(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "notadmin@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    task_id = await _create_task(client, headers, list_id, "Temp")

    response = await client.delete(f"/v1/tasks/{task_id}/permanent", headers=headers)

    assert response.status_code == 403


async def test_get_deleted_tasks_as_admin_returns_soft_deleted_tasks(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "admin3@example.com"
    headers = await _register_and_login(client, email)
    list_id = await _create_task_list(client, headers, "Groceries")
    task_id = await _create_task(client, headers, list_id, "Temp")
    await client.delete(f"/v1/tasks/{task_id}", headers=headers)
    await _promote_to_admin(db_session, email)

    response = await client.get("/v1/tasks/deleted", headers=headers)

    assert response.status_code == 200
    assert [task["id"] for task in response.json()] == [task_id]


async def test_get_deleted_tasks_as_non_admin_returns_403(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "notadmin2@example.com")

    response = await client.get("/v1/tasks/deleted", headers=headers)

    assert response.status_code == 403


async def test_get_task_returns_404_after_soft_delete(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "owner4@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    task_id = await _create_task(client, headers, list_id, "Temp")
    await client.delete(f"/v1/tasks/{task_id}", headers=headers)

    response = await client.get(f"/v1/tasks/{task_id}", headers=headers)

    assert response.status_code == 404


async def test_list_tasks_excludes_soft_deleted_tasks(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "owner5@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    kept_id = await _create_task(client, headers, list_id, "Kept")
    removed_id = await _create_task(client, headers, list_id, "Removed")
    await client.delete(f"/v1/tasks/{removed_id}", headers=headers)

    response = await client.get("/v1/tasks", headers=headers)

    assert response.status_code == 200
    task_ids = [task["id"] for task in response.json()]
    assert kept_id in task_ids
    assert removed_id not in task_ids
