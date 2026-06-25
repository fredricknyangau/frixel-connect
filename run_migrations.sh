#!/usr/bin/env bash
# =============================================================================
# run_migrations.sh
# Applies all SQL migration files in order against the wifi_billing database.
#
# Usage:
#   ./run_migrations.sh
#
# This script connects to the database INSIDE the Docker Compose network
# by using `docker compose exec db`. This avoids any host port-binding issues
# and works whether or not port 5432 is exposed to the host machine.
#
# If you want to run it against a local PostgreSQL (not Docker), set:
#   USE_DOCKER=false DB_HOST=localhost DB_PORT=5432 ./run_migrations.sh
#
# Idempotency:
#   All CREATE TABLE statements use IF NOT EXISTS, so running this script
#   twice does NOT duplicate tables.
#
#   WHERE IF NOT EXISTS CANNOT be used:
#   - UNIQUE constraints inside CREATE TABLE: PostgreSQL does not support
#     IF NOT EXISTS on inline constraint definitions. However, since the
#     CREATE TABLE itself is guarded by IF NOT EXISTS, on the second run
#     the whole CREATE TABLE statement is skipped, so constraint duplication
#     never happens.
#   - CREATE INDEX: We use CREATE INDEX IF NOT EXISTS (PG 9.5+), which is safe.
#   - ALTER TABLE: We don't use ALTER TABLE in these migrations. If we did,
#     we would need a function that checks pg_constraint before applying.
# =============================================================================

# Exit immediately if any command returns a non-zero exit code.
# This is the most important line in the script: a failed migration must
# stop everything loudly rather than silently continuing to the next file.
set -e

# Force strictly ASCII collation for predictable migration order
# Otherwise, LC_COLLATE ignores underscores and sorts '009b' before '009_create'
export LC_ALL=C

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_USER="${DB_USER:-zealnet}"
DB_PASS="${DB_PASS:-zealnet}"
DB_NAME="${DB_NAME:-wifi_billing}"

# USE_DOCKER=true means we connect via `docker compose exec db psql`.
# This is the default and avoids host port binding issues.
USE_DOCKER="${USE_DOCKER:-true}"

# Only used when USE_DOCKER=false
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# The directory containing the migration files, relative to this script.
MIGRATIONS_DIR="$(cd "$(dirname "$0")/migrations" && pwd)"


echo "============================================================"
echo "  WiFi Billing System -Database Migration Runner"
echo "============================================================"
if [ "$USE_DOCKER" = "true" ]; then
    echo "  Mode:     Docker Compose (docker compose exec db)"
else
    echo "  Mode:     Direct connection"
    echo "  Host:     $DB_HOST:$DB_PORT"
fi
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo "  Dir:      $MIGRATIONS_DIR"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Helper function: runs psql with a given SQL file.
# Abstracts over Docker vs. direct connection.
# ---------------------------------------------------------------------------
run_psql() {
    local sql_file="$1"

    if [ "$USE_DOCKER" = "true" ]; then
        # We pipe the file content through docker compose exec.
        # -T disables pseudo-TTY allocation (required for piping input).
        # -v ON_ERROR_STOP=1: psql exits non-zero on SQL error (defeats set -e otherwise).
        docker compose exec -T db \
            psql \
            --username="$DB_USER" \
            --dbname="$DB_NAME" \
            -v ON_ERROR_STOP=1 \
            < "$sql_file"
    else
        export PGPASSWORD="$DB_PASS"
        psql \
            --host="$DB_HOST" \
            --port="$DB_PORT" \
            --username="$DB_USER" \
            --dbname="$DB_NAME" \
            -v ON_ERROR_STOP=1 \
            --file="$sql_file"
    fi
}

# ---------------------------------------------------------------------------
# Apply each migration file in lexicographic order (001_, 002_, …).
# ---------------------------------------------------------------------------
for migration_file in "$MIGRATIONS_DIR"/*.sql; do
    filename=$(basename "$migration_file")
    echo "▶  Applying: $filename"
    run_psql "$migration_file"
    echo "✓  Done:     $filename"
    echo ""
done

echo "============================================================"
echo "  All migrations applied successfully."
echo "============================================================"
