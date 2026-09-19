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


async def test_delete_task_as_regular_user_returns_403(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "regular@example.com")
    list_id = await _create_task_list(client, headers, "Groceries")
    created = await client.post(
        "/v1/tasks", json={"title": "Temp", "list_id": list_id}, headers=headers
    )
    task_id = created.json()["id"]

    response = await client.delete(f"/v1/tasks/{task_id}", headers=headers)

    assert response.status_code == 403


async def test_delete_task_as_admin_returns_204(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "admin@example.com"
    headers = await _register_and_login(client, email)
    list_id = await _create_task_list(client, headers, "Groceries")
    created = await client.post(
        "/v1/tasks", json={"title": "Temp", "list_id": list_id}, headers=headers
    )
    task_id = created.json()["id"]

    # Registration never grants admin; promote directly in the store, the way
    # a real deployment would via an internal tool, not a self-service endpoint.
    result = await db_session.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one()
    user.role = UserRole.ADMIN
    await db_session.commit()

    response = await client.delete(f"/v1/tasks/{task_id}", headers=headers)

    assert response.status_code == 204
