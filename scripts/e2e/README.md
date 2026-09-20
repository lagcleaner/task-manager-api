# Manual e2e flow scripts

Pytest files that drive the real, running API over plain HTTP (`httpx.AsyncClient` against a
base URL — no `ASGITransport`, no test DB). They exercise the actual Postgres/Redis-backed
stack the way a real client would. These are **not** part of `uv run pytest` (`testpaths =
["tests"]` in `pyproject.toml` excludes this directory) and are not wired into pre-commit or
CI — run them manually, on demand.

## Running (automatic, local stack)

```bash
make e2e                              # all four flows, admin steps included
scripts/e2e/run.sh scripts/e2e/test_tasks_flow.py -v   # args pass through to pytest
```

`scripts/e2e/run.sh` starts the docker compose stack (`docker compose up --build -d`),
waits for `GET /v1/health`, provisions a fixed e2e admin account (register + promote via
`docker compose exec db psql`, same as the manual steps below), then runs
`uv run pytest scripts/e2e --no-cov` with `E2E_ADMIN_EMAIL`/`E2E_ADMIN_PASSWORD` set, so
every admin-gated step runs instead of skipping. Idempotent — safe to re-run. Leaves the
stack running afterward (same as `make local-run`); set `E2E_DOWN_AFTER=1` to tear it down
when the run finishes. Only targets the local compose stack — see the script's header
comment if pointing `E2E_BASE_URL` somewhere else.

## Running (manual)

The stack must already be running:

```bash
docker compose up --build   # or: make local-run
```

API reachable at `http://localhost:8000` by default (health check: `GET /v1/health`).

```bash
uv run pytest scripts/e2e --no-cov              # all four flows
uv run pytest scripts/e2e/test_auth_flow.py --no-cov   # a single flow
```

`--no-cov` skips coverage collection (`pyproject.toml`'s `addopts` enables it by default,
which isn't meaningful for scripts that don't import `app`). Without `E2E_ADMIN_EMAIL`/
`E2E_ADMIN_PASSWORD` set (see Configuration below), admin-gated steps skip.

## Configuration

- `E2E_BASE_URL` — base URL of the running API. Default: `http://localhost:8000`.
- `E2E_ALLOW_REMOTE=1` — required to point these scripts at anything that doesn't look like
  localhost/loopback/a private network host. Without it, a non-dev-looking `E2E_BASE_URL`
  (e.g. a public hostname) is refused at collection time — this is meant to make it hard to
  accidentally run destructive, data-creating scripts against a real environment.
- `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` — optional. The plain `DELETE /v1/tasks/{id}` and
  `DELETE /v1/task-lists/{id}` routes are self-service soft-delete (owner-only) and don't
  need admin. `DELETE /v1/tasks/{id}/permanent`, `DELETE /v1/task-lists/{id}/permanent`,
  `GET /v1/tasks/deleted`, and `GET /v1/task-lists/deleted` do require the `admin` role, and
  this API has no self-service promotion endpoint (see the main `README.md`'s API flow
  section — promote a user via a direct DB write). Set both to a pre-provisioned admin
  account's credentials to exercise `test_task_lists_flow.py`'s admin-only tail
  (deleted-listing + permanent hard-delete) and to let it and `test_tasks_flow.py` actually
  hard-delete the task list they created, instead of leaving it soft-deleted. Without them,
  those flows still run everything else and `pytest.skip` (or fall back to soft-delete-only
  cleanup) at the admin-gated step — reruns stay safe, but soft-deleted task lists/tasks
  accumulate in the target DB until an admin account is provisioned.

Use `make e2e` / `scripts/e2e/run.sh` (see above) to get this done automatically. To
provision a local admin account by hand instead:

```bash
# 1. register a normal user via the API (or reuse one), then promote it directly in Postgres:
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "UPDATE users SET role = 'ADMIN' WHERE email = 'admin@example.com';"
```

## What each file covers

- `test_auth_flow.py` — register -> login -> use access token -> refresh (rotation
  verified) -> logout -> access token rejected after logout, plus a duplicate-registration
  failure path. Stays comfortably under the `10/minute` `rate_limit_auth` budget.
- `test_tasks_flow.py` — create task list -> create/list/get/update/change-status/assign
  task -> owner soft-deletes task -> verify 404 -> (admin) sees it in
  `GET /v1/tasks/deleted` -> admin hard-deletes via `/permanent` -> gone from the listing.
- `test_task_lists_flow.py` — create/list/get/update task list -> list its tasks filtered by
  status and priority -> owner soft-deletes list -> verify 404 -> (admin) sees it in
  `GET /v1/task-lists/deleted`, confirms cascade soft-deleted its two tasks
  (`GET /v1/tasks/deleted`) -> admin hard-deletes list via `/permanent` -> confirms cascade
  hard-deleted the tasks too.
- `test_invitations_flow.py` — create task list -> invite a unique email -> list invitations
  -> verify it appears.

Every script generates its own uuid4-suffixed emails/titles (`unique_email`/`unique_title`
fixtures in `conftest.py`) and cleans up what it created in a `finally` block, so re-running
against the same stack is safe.
