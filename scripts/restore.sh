#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: ./scripts/restore.sh <backup_file.sql.gz> [target_database_name]"
  echo "Example: ./scripts/restore.sh backup_wifi_billing_20260618_100000.sql.gz"
  exit 1
fi

FILE=$1
# Default to creating a test restore database so we don't accidentally overwrite production
DB_NAME=${2:-wifi_billing_restore_test}

if [ ! -f "$FILE" ]; then
    echo "Error: File $FILE not found!"
    exit 1
fi

echo "=========================================================="
echo "Starting Database Restore Drill"
echo "Source File: $FILE"
echo "Target DB:   $DB_NAME"
echo "=========================================================="

echo "[1/3] Terminating existing connections and dropping/creating target DB..."
docker compose exec -T db psql -U frixel -d postgres -c "
    SELECT pg_terminate_backend(pg_stat_activity.pid)
    FROM pg_stat_activity
    WHERE pg_stat_activity.datname = '$DB_NAME' AND pid <> pg_backend_pid();
" > /dev/null 2>&1 || true

docker compose exec -T db psql -U frixel -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker compose exec -T db psql -U frixel -d postgres -c "CREATE DATABASE $DB_NAME;"

echo "[2/3] Extracting and importing data into $DB_NAME..."
# gunzip streams the decompressed sql directly into the container's psql process
gunzip -c "$FILE" | docker compose exec -T db psql -U frixel -d "$DB_NAME" > /dev/null

echo "[3/3] Restore complete! You can connect to verify:"
echo "docker compose exec db psql -U frixel -d $DB_NAME"
