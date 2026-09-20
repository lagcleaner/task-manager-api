#!/usr/bin/env bash
# Runs the manual e2e flow scripts (scripts/e2e/) against the local docker compose
# stack, auto-provisioning the admin account they need instead of requiring it to be
# set up by hand first.
#
# Only targets the local docker-compose stack: it starts/health-checks that stack and
# promotes a user to admin via `docker compose exec db psql`. It does not know about
# E2E_BASE_URL pointing anywhere else — for a non-local target, provision an admin and
# export E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD yourself, then run
# `uv run pytest scripts/e2e` directly (see README.md).
#
# Idempotent: safe to re-run. Leaves the stack running afterward (same as
# `make local-run`) unless E2E_DOWN_AFTER=1 is set.
#
# Usage: scripts/e2e/run.sh [pytest args...]
#   scripts/e2e/run.sh                          # run all four flows
#   scripts/e2e/run.sh scripts/e2e/test_tasks_flow.py -v
#   E2E_DOWN_AFTER=1 scripts/e2e/run.sh          # tear the stack down when done
set -euo pipefail

cd "$(dirname "$0")/../.."

ADMIN_EMAIL="e2e-bootstrap-admin@example.com"
# Fixed, test-only password satisfying UserCreate's strength rule (12+ chars, letter + digit).
ADMIN_PASSWORD="correct-horse-e2e-admin1"
BASE_URL="http://localhost:8000"

bash scripts/generate_env.sh

echo "Starting docker compose stack..."
docker compose up --build -d

echo "Waiting for the API to become healthy..."
for _ in $(seq 1 30); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/v1/health")" = "200" ]; then
    break
  fi
  sleep 2
done
if [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/v1/health")" != "200" ]; then
  echo "API never became healthy at $BASE_URL/v1/health. Check: docker compose logs api" >&2
  exit 1
fi

echo "Provisioning e2e admin account ($ADMIN_EMAIL)..."
register_status=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$ADMIN_EMAIL\", \"password\": \"$ADMIN_PASSWORD\"}")
if [ "$register_status" != "201" ] && [ "$register_status" != "409" ]; then
  echo "Unexpected status $register_status registering the e2e admin account." >&2
  exit 1
fi

# .env holds the app-role Postgres credentials docker compose already injects into the
# db/api containers; source it to get POSTGRES_USER/POSTGRES_DB for the psql exec below.
set -a
# shellcheck disable=SC1091
source .env
set +a

docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "UPDATE users SET role = 'ADMIN' WHERE email = '$ADMIN_EMAIL';" > /dev/null

login_status=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$ADMIN_EMAIL\", \"password\": \"$ADMIN_PASSWORD\"}")
if [ "$login_status" != "200" ]; then
  echo "e2e admin account provisioned but login failed with $login_status. Auth rate limit may be exhausted." >&2
  exit 1
fi

echo "Running e2e flows..."
test_status=0
E2E_ADMIN_EMAIL="$ADMIN_EMAIL" E2E_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  uv run pytest scripts/e2e --no-cov "$@" || test_status=$?

if [ "${E2E_DOWN_AFTER:-}" = "1" ]; then
  echo "Stopping docker compose stack (E2E_DOWN_AFTER=1)..."
  docker compose down
fi

exit $test_status
