# Manual e2e flow scripts

Pytest files that drive the real, running API over plain HTTP (`httpx.AsyncClient` against a
base URL — no `ASGITransport`, no test DB). They exercise the actual Postgres/Redis-backed
stack the way a real client would. These are **not** part of `uv run pytest` (`testpaths =
["tests"]` in `pyproject.toml` excludes this directory) and are not wired into pre-commit or
CI — run them manually, on demand.

## Prerequisites

The stack must already be running:

```bash
docker compose up --build   # or: make local-run
```

API reachable at `http://localhost:8000` by default (health check: `GET /v1/health`).

## Running

```bash
uv run pytest scripts/e2e --no-cov              # all four flows
uv run pytest scripts/e2e/test_auth_flow.py --no-cov   # a single flow
```

`--no-cov` skips coverage collection (`pyproject.toml`'s `addopts` enables it by default,
which isn't meaningful for scripts that don't import `app`).

## Configuration

- `E2E_BASE_URL` — base URL of the running API. Default: `http://localhost:8000`.
- `E2E_ALLOW_REMOTE=1` — required to point these scripts at anything that doesn't look like
  localhost/loopback/a private network host. Without it, a non-dev-looking `E2E_BASE_URL`
  (e.g. a public hostname) is refused at collection time — this is meant to make it hard to
  accidentally run destructive, data-creating scripts against a real environment.
- `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` — optional. `DELETE /v1/tasks/{id}` and
  `DELETE /v1/task-lists/{id}` require the `admin` role, and this API has no self-service
  promotion endpoint (see the main `README.md`'s API flow section — promote a user via a
  direct DB write). Set both to a pre-provisioned admin account's credentials to exercise the
  delete/404 steps in `test_tasks_flow.py` and `test_task_lists_flow.py`, and to let those
  scripts (plus `test_invitations_flow.py`) actually delete the task list they created.
  Without them, those flows still run everything they can and `pytest.skip` at the
  admin-gated step, and cleanup best-effort no-ops — reruns stay safe, but created task
  lists/tasks accumulate in the target DB until an admin account is provisioned.

To provision a local admin account for this:

```bash
# 1. register a normal user via the API (or reuse one), then promote it directly in Postgres:
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "UPDATE users SET role = 'ADMIN' WHERE email = 'admin@example.com';"
```

## What each file covers

- `test_auth_flow.py` — register -> login -> use access token -> refresh (rotation
  verified) -> logout -> access token rejected after logout, plus a duplicate-registration
  failure path. Stays comfortably under the `10/minute` `rate_limit_auth` budget.
- `test_tasks_flow.py` — create task list -> create/list/get/update/change-status/assign/
  delete task -> verify 404.
- `test_task_lists_flow.py` — create/list/get/update task list -> list its tasks filtered by
  status and priority -> delete -> verify 404.
- `test_invitations_flow.py` — create task list -> invite a unique email -> list invitations
  -> verify it appears.

Every script generates its own uuid4-suffixed emails/titles (`unique_email`/`unique_title`
fixtures in `conftest.py`) and cleans up what it created in a `finally` block, so re-running
against the same stack is safe.
