"""Manual e2e flow: create task list -> list task lists -> get task list -> update
task list -> list its tasks with status/priority filters -> owner soft-deletes the list
-> verify 404 -> (if admin available) admin sees it in GET /v1/task-lists/deleted and
hard-deletes it via DELETE /v1/task-lists/{id}/permanent.

Run: uv run pytest scripts/e2e/test_task_lists_flow.py --no-cov (requires a live stack,
see README.md).

DELETE /v1/task-lists/{id} is self-service soft-delete, owner-only — no admin needed.
The admin-only tail (deleted-listing + permanent hard-delete) needs E2E_ADMIN_EMAIL/
E2E_ADMIN_PASSWORD set to a pre-provisioned admin account; without them this flow still
exercises everything else including the soft-delete/404 step, and only that tail is
skipped, leaving the (soft-deleted, already invisible) list behind.

Uses the shared `actor` fixture (conftest.py) instead of registering its own user — see
that fixture's docstring for why.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient


async def test_create_list_update_filter_tasks_delete_flow(
    client: AsyncClient,
    unique_title: Callable[[str], str],
    admin_headers: dict[str, str] | None,
    actor: tuple[dict[str, str], str],
) -> None:
    headers, _user_id = actor

    # create task list
    list_name = unique_title("Task List")
    create_response = await client.post("/v1/task-lists", json={"name": list_name}, headers=headers)
    assert create_response.status_code == 201
    list_id = create_response.json()["id"]

    try:
        # list task lists
        list_lists_response = await client.get("/v1/task-lists", headers=headers)
        assert list_lists_response.status_code == 200
        assert any(item["id"] == list_id for item in list_lists_response.json())

        # get task list
        get_response = await client.get(f"/v1/task-lists/{list_id}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["name"] == list_name

        # update task list
        updated_name = unique_title("Task List Updated")
        update_response = await client.patch(
            f"/v1/task-lists/{list_id}", json={"name": updated_name}, headers=headers
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == updated_name

        # seed two tasks with different status/priority to exercise the filters
        high_priority = await client.post(
            "/v1/tasks",
            json={"title": unique_title("Urgent"), "list_id": list_id, "priority": "high"},
            headers=headers,
        )
        assert high_priority.status_code == 201
        high_priority_id = high_priority.json()["id"]

        low_priority = await client.post(
            "/v1/tasks",
            json={"title": unique_title("Whenever"), "list_id": list_id, "priority": "low"},
            headers=headers,
        )
        assert low_priority.status_code == 201
        low_priority_id = low_priority.json()["id"]
        completed_response = await client.patch(
            f"/v1/tasks/{low_priority_id}/status", json={"status": "completed"}, headers=headers
        )
        assert completed_response.status_code == 200

        # list tasks for the list, filtered by status
        status_filtered = await client.get(
            f"/v1/task-lists/{list_id}/tasks", params={"status": "completed"}, headers=headers
        )
        assert status_filtered.status_code == 200
        status_filtered_ids = [item["id"] for item in status_filtered.json()["tasks"]]
        assert status_filtered_ids == [low_priority_id]

        # list tasks for the list, filtered by priority
        priority_filtered = await client.get(
            f"/v1/task-lists/{list_id}/tasks", params={"priority": "high"}, headers=headers
        )
        assert priority_filtered.status_code == 200
        priority_filtered_ids = [item["id"] for item in priority_filtered.json()["tasks"]]
        assert priority_filtered_ids == [high_priority_id]

        # owner soft-deletes the task list (self-service, no admin needed)
        delete_response = await client.delete(f"/v1/task-lists/{list_id}", headers=headers)
        assert delete_response.status_code == 204

        # verify 404 after soft-delete
        after_delete_response = await client.get(f"/v1/task-lists/{list_id}", headers=headers)
        assert after_delete_response.status_code == 404

        if admin_headers is None:
            pytest.skip(
                "E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD not set: GET /v1/task-lists/deleted and "
                "DELETE /v1/task-lists/{id}/permanent require the admin role, which this API "
                "has no self-service way to grant. See scripts/e2e/README.md. The soft-deleted "
                "list is left behind (already invisible to non-admin callers)."
            )

        # admin sees the soft-deleted list
        deleted_response = await client.get("/v1/task-lists/deleted", headers=admin_headers)
        assert deleted_response.status_code == 200
        assert any(item["id"] == list_id for item in deleted_response.json())

        # admin permanently hard-deletes it
        permanent_response = await client.delete(
            f"/v1/task-lists/{list_id}/permanent", headers=admin_headers
        )
        assert permanent_response.status_code == 204

        # gone from the deleted-listing too, now that it's hard-deleted
        deleted_after_response = await client.get("/v1/task-lists/deleted", headers=admin_headers)
        assert deleted_after_response.status_code == 200
        assert not any(item["id"] == list_id for item in deleted_after_response.json())
    finally:
        if admin_headers is not None:
            # Best-effort: no-op (404) if the try block already hard-deleted it, so reruns
            # stay idempotent regardless of where an earlier assertion failed.
            await client.delete(f"/v1/task-lists/{list_id}/permanent", headers=admin_headers)
        else:
            # No admin available for a real cleanup — at least soft-delete so the list stops
            # showing up in normal listings. No-op (404) if the try block already did this.
            await client.delete(f"/v1/task-lists/{list_id}", headers=headers)
