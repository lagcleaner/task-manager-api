"""Manual e2e flow: create task list -> invite a second (unique) email to it -> list
invitations for the list -> verify the invited email appears -> re-invite the same email
while still live is still blocked (409). Cleans up the task list.

Run: uv run pytest scripts/e2e/test_invitations_flow.py --no-cov (requires a live stack,
see README.md).

Cleanup (DELETE /v1/task-lists/{id}) is self-service soft-delete, owner-only — no admin
needed, and always runs. The invite/list steps this file actually tests don't need admin
at all either; `admin_headers` is unused here now.

Uses the shared `actor` fixture (conftest.py) as the inviter instead of registering its own
user — see that fixture's docstring for why. The invited email still comes from
`unique_email`, so there's no collision with the shared actor or between reruns.

Re: ADR-018 (partial unique index / soft-delete-aware duplicate check on invitations) — the
"re-invite the same email after a cancel/decline succeeds" scenario from that ADR is NOT
covered here. There is no per-invitation cancel/decline endpoint in this API; the only
invitation soft-delete path is the cascade from `DELETE /v1/task-lists/{id}`, which also
soft-deletes the list itself, so any further POST to that list_id's invitations 404s before
reaching the duplicate check. That scenario is untestable at the HTTP level until such an
endpoint exists (see ADR-018's Negative section). What IS covered here, and does regress if
the duplicate-check filter is ever loosened incorrectly: duplicate-inviting a still-live
email to a still-live list stays blocked.
"""

from collections.abc import Callable

from httpx import AsyncClient


async def test_invite_and_list_invitations_flow(
    client: AsyncClient,
    unique_email: Callable[[str], str],
    unique_title: Callable[[str], str],
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

        # re-inviting the same email while it's still live is still blocked (ADR-018:
        # the soft-delete-aware duplicate check only excludes deleted_at rows, not live ones)
        duplicate_invite_response = await client.post(
            f"/v1/task-lists/{list_id}/invitations",
            json={"email": invited_email},
            headers=headers,
        )
        assert duplicate_invite_response.status_code == 409
    finally:
        await client.delete(f"/v1/task-lists/{list_id}", headers=headers)
