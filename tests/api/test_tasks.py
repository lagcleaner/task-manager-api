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


async def test_create_task_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/v1/tasks", json={"title": "Write tests"})

    assert response.status_code == 401


async def test_create_task_returns_201(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "creator@example.com")

    response = await client.post("/v1/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Write tests"
    assert body["status"] == "pending"


async def test_get_task_returns_404_when_missing(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "reader@example.com")

    response = await client.get("/v1/tasks/999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


async def test_list_tasks_returns_created_tasks(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "lister@example.com")
    await client.post("/v1/tasks", json={"title": "First"}, headers=headers)
    await client.post("/v1/tasks", json={"title": "Second"}, headers=headers)

    response = await client.get("/v1/tasks", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_update_task_changes_status(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "updater@example.com")
    created = await client.post("/v1/tasks", json={"title": "Ship feature"}, headers=headers)
    task_id = created.json()["id"]

    response = await client.patch(
        f"/v1/tasks/{task_id}", json={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


async def test_delete_task_as_regular_user_returns_403(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "regular@example.com")
    created = await client.post("/v1/tasks", json={"title": "Temp"}, headers=headers)
    task_id = created.json()["id"]

    response = await client.delete(f"/v1/tasks/{task_id}", headers=headers)

    assert response.status_code == 403


async def test_delete_task_as_admin_returns_204(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "admin@example.com"
    headers = await _register_and_login(client, email)
    created = await client.post("/v1/tasks", json={"title": "Temp"}, headers=headers)
    task_id = created.json()["id"]

    # Registration never grants admin; promote directly in the store, the way
    # a real deployment would via an internal tool, not a self-service endpoint.
    result = await db_session.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one()
    user.role = UserRole.ADMIN
    await db_session.commit()

    response = await client.delete(f"/v1/tasks/{task_id}", headers=headers)

    assert response.status_code == 204
