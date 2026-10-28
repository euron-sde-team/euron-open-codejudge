#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh into the running local stack. Replaces the
# database contents and re-uploads the objects. Stops the API, worker and judges first so
# nothing writes while the database is replaced.
#   make restore BACKUP=backups/<timestamp>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:?usage: scripts/restore.sh backups/<timestamp>}"
[[ "$SRC" = /* ]] || SRC="$ROOT/$SRC"
[[ -f "$SRC/codejudge.dump" ]] || { echo "no codejudge.dump in $SRC"; exit 1; }
COMPOSE=(docker compose --env-file "$ROOT/deploy/compose/.env" -f "$ROOT/deploy/compose/compose.yaml" -f "$ROOT/deploy/compose/compose.floci.yaml")

"${COMPOSE[@]}" stop api worker judge web
"${COMPOSE[@]}" exec -T postgres pg_restore -U codejudge -d codejudge --clean --if-exists --no-owner < "$SRC/codejudge.dump"
docker run --rm --network codejudge_default -v "$SRC/objects:/backup:ro" \
  -e AWS_ACCESS_KEY_ID=test -e AWS_SECRET_ACCESS_KEY=test -e AWS_DEFAULT_REGION=us-east-1 \
  amazon/aws-cli:2.22.0 --endpoint-url http://floci:4566 s3 sync /backup s3://codejudge-local-objects --only-show-errors
"${COMPOSE[@]}" up -d --wait api worker judge web
echo "restored ${SRC#"$ROOT"/}"
