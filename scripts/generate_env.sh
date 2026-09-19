#!/usr/bin/env bash
# Generates a local .env from .env.example with freshly generated secrets.
# Idempotent: never overwrites an existing .env.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env already exists, leaving it untouched."
  exit 0
fi

cp .env.example .env

# Replace by variable name, never by placeholder text: some placeholders in
# .env.example are byte-for-byte identical across unrelated keys (e.g.
# POSTGRES_SUPERUSER_PASSWORD and REDIS_PASSWORD), so a text-based replace
# would assign the same secret to both. awk matches the exact `KEY=` line
# instead, and building the line via string concat (not a regex substitution)
# avoids breaking on `/`/`+` characters that base64 output can contain.
set_secret() {
  key="$1"
  value="$2"
  awk -F= -v key="$key" -v val="$value" 'BEGIN{OFS="="} $1==key{$0=key"="val} {print}' .env > .env.tmp
  mv .env.tmp .env
}

set_secret POSTGRES_SUPERUSER_PASSWORD "$(openssl rand -base64 24)"
set_secret POSTGRES_MIGRATOR_PASSWORD "$(openssl rand -base64 24)"
set_secret POSTGRES_PASSWORD "$(openssl rand -base64 24)"
set_secret JWT_SECRET_KEY "$(openssl rand -hex 32)"
set_secret REDIS_PASSWORD "$(openssl rand -base64 24)"

echo "Generated .env with fresh local secrets."
