#!/bin/bash
set -e

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="backup_wifi_billing_$TIMESTAMP.sql.gz"

echo "Starting database backup..."
# We use -T to disable pseudo-TTY allocation because this script might run in cron
docker compose exec -T db pg_dump -U frixel wifi_billing | gzip > "$FILENAME"

echo "Backup successfully created: $FILENAME"

# ----------------------------------------------------------------------
# DEPLOYMENT CONFIGURATION POINT:
# Configure your object storage upload command below (e.g. AWS S3, R2).
# ----------------------------------------------------------------------
# aws s3 cp "$FILENAME" s3://Frixel Connect-db-backups/
# rm "$FILENAME" # optionally clean up local file after upload
