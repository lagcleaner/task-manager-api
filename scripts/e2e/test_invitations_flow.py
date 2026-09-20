"""Manual e2e flow: create task list -> invite a second (unique) email to it -> list
invitations for the list -> verify the invited email appears. Cleans up the task list.

Run: uv run pytest scripts/e2e/test_invitations_flow.py --no-cov (requires a live stack,
see README.md).

Cleanup (DELETE /v1/task-lists/{id}) requires the admin role, so it only runs when
E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD are set to a pre-provisioned admin account — see
README.md. The invite/list steps this file actually tests don't need admin at all.

Uses the shared `actor` fixture (conftest.py) as the inviter instead of registering its own
user — see that fixture's docstring for why. The invited email still comes from
`unique_email`, so there's no collision with the shared actor or between reruns.
"""

from collections.abc import Callable

from httpx import AsyncClient


async def test_invite_and_list_invitations_flow(
    client: AsyncClient,
    unique_email: Callable[[str], str],
    unique_title: Callable[[str], str],
    admin_headers: dict[str, str] | None,
    actor: tuple[dict[str, str], str],
) -> None:
    headers, _user_id = actor

    # create task list
    list_response = await client.post(
        "/v1/task-lists", json={"name": unique_title("Invitations Flow List")}, headers=headers
    )
    assert list_response.status_code == 201
    list_id = list_response.json()["id"]

    try:
        # invite a second, uniquely generated email to it
        invited_email = unique_email("invitee")
        invite_response = await client.post(
            f"/v1/task-lists/{list_id}/invitations",
            json={"email": invited_email},
            headers=headers,
        )
        assert invite_response.status_code == 201
        assert invite_response.json()["email"] == invited_email

        # list invitations for the list, verify the invited email appears
        list_invitations_response = await client.get(
            f"/v1/task-lists/{list_id}/invitations", headers=headers
        )
        assert list_invitations_response.status_code == 200
        invited_emails = {item["email"] for item in list_invitations_response.json()}
        assert invited_email in invited_emails
    finally:
        if admin_headers is not None:
            await client.delete(f"/v1/task-lists/{list_id}", headers=admin_headers)
