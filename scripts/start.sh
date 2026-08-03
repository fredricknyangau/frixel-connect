#!/usr/bin/env bash
set -e

export USE_DOCKER=${USE_DOCKER:-false}

if [[ "$USE_DOCKER" == "true" ]]; then
  echo "Running database migrations..."
  # Configure variables for the migration script to run directly
  export USE_DOCKER=false
  export DB_HOST=${DB_HOST:-db}
  export DB_PORT=${DB_PORT:-5432}
  export DB_USER=${POSTGRES_USER:-frixel}
  export DB_PASS=${POSTGRES_PASSWORD:-frixel}
  export DB_NAME=${POSTGRES_DB:-wifi_billing}

  # Wait for database to be ready
  until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"; do
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    sleep 2
  done

  bash scripts/run_migrations.sh

  echo "Seeding database..."
  python scripts/seed_db.py
fi

echo "Starting application..."
exec "$@"
