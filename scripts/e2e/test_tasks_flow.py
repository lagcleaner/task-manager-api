"""Manual e2e flow: create task list -> create task -> list tasks -> get task ->
update task -> change status -> assign task -> owner soft-deletes the task -> verify
404 -> (if admin available) admin sees it in GET /v1/tasks/deleted and hard-deletes it
via DELETE /v1/tasks/{id}/permanent. Cleans up the task list it created.

Run: uv run pytest scripts/e2e/test_tasks_flow.py --no-cov (requires a live stack, see README.md).

DELETE /v1/tasks/{id} is self-service soft-delete, owner-only (resolved through the
task's parent list) — no admin needed. The admin-only tail (deleted-listing + permanent
hard-delete) and the real cleanup of the task list (hard-delete via
DELETE /v1/task-lists/{id}/permanent) need E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD set to a
pre-provisioned admin account; without them this flow still exercises everything else,
only that tail is skipped, and cleanup falls back to soft-deleting the list instead of
failing.

Uses the shared `actor` fixture (conftest.py) instead of registering its own user — see
that fixture's docstring for why.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient


async def test_create_list_use_update_assign_delete_task_flow(
    client: AsyncClient,
    unique_title: Callable[[str], str],
    admin_headers: dict[str, str] | None,
    actor: tuple[dict[str, str], str],
) -> None:
    headers, user_id = actor

    # create the task's parent task list
    list_response = await client.post(
        "/v1/task-lists", json={"name": unique_title("Tasks Flow List")}, headers=headers
    )
    assert list_response.status_code == 201
    list_id = list_response.json()["id"]

    try:
        # create task
        task_title = unique_title("Task")
        create_response = await client.post(
            "/v1/tasks", json={"title": task_title, "list_id": list_id}, headers=headers
        )
        assert create_response.status_code == 201
        task = create_response.json()
        task_id = task["id"]
        assert task["title"] == task_title
        assert task["status"] == "pending"

        # list tasks
        list_tasks_response = await client.get("/v1/tasks", headers=headers)
        assert list_tasks_response.status_code == 200
        assert any(item["id"] == task_id for item in list_tasks_response.json())

        # get task
        get_response = await client.get(f"/v1/tasks/{task_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["id"] == task_id

        # update task
        updated_title = unique_title("Task Updated")
        update_response = await client.patch(
            f"/v1/tasks/{task_id}", json={"title": updated_title}, headers=headers
        )
        assert update_response.status_code == 200
        assert update_response.json()["title"] == updated_title

        # change task status
        status_response = await client.patch(
            f"/v1/tasks/{task_id}/status", json={"status": "in_progress"}, headers=headers
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "in_progress"

        # assign task (to its own creator, no second account needed)
        assign_response = await client.patch(
            f"/v1/tasks/{task_id}/assignee", json={"assignee_id": user_id}, headers=headers
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["assignee_id"] == user_id

        # owner (via the parent list's ownership) soft-deletes the task
        delete_response = await client.delete(f"/v1/tasks/{task_id}", headers=headers)
        assert delete_response.status_code == 204

        # verify 404 after soft-delete
        after_delete_response = await client.get(f"/v1/tasks/{task_id}", headers=headers)
        assert after_delete_response.status_code == 404

        if admin_headers is None:
            pytest.skip(
                "E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD not set: GET /v1/tasks/deleted and "
                "DELETE /v1/tasks/{id}/permanent require the admin role, which this API "
                "has no self-service way to grant. See scripts/e2e/README.md. The "
                "soft-deleted task is left behind (already invisible to non-admin callers)."
            )

        # admin sees the soft-deleted task
        deleted_response = await client.get("/v1/tasks/deleted", headers=admin_headers)
        assert deleted_response.status_code == 200
        assert any(item["id"] == task_id for item in deleted_response.json())

        # admin permanently hard-deletes it
        permanent_response = await client.delete(
            f"/v1/tasks/{task_id}/permanent", headers=admin_headers
        )
        assert permanent_response.status_code == 204

        # gone from the deleted-listing too, now that it's hard-deleted
        deleted_after_response = await client.get("/v1/tasks/deleted", headers=admin_headers)
        assert deleted_after_response.status_code == 200
        assert not any(item["id"] == task_id for item in deleted_after_response.json())
    finally:
        if admin_headers is not None:
            # Real cleanup: hard-delete the task list (and any remaining child rows).
            await client.delete(f"/v1/task-lists/{list_id}/permanent", headers=admin_headers)
        else:
            # No admin available — at least soft-delete the list so it stops showing up.
            await client.delete(f"/v1/task-lists/{list_id}", headers=headers)
