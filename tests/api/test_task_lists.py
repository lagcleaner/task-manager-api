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
