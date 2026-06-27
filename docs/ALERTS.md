# ZealSync Observability & Alerting Thresholds

This document outlines the operational health metrics exposed by ZealSync's `/metrics` endpoint and the recommended thresholds for configuring alerts (e.g., in Prometheus/Alertmanager, Datadog, or New Relic).

## 1. Webhook Failure Rate
**Metric**: `webhook_events_total{status="error"}` / `webhook_events_total{status="received"}`
- **Threshold**: `> 5%` failure rate over a rolling `10m` window.
- **Why**: Daraja webhook failures mean M-Pesa is notifying us of successful payments, but we are failing to process them (e.g. DB is down, or schema changed). This directly leads to customers paying but not receiving internet.
- **Action**: Check `api` container logs for `Exception` stack traces matching the `process_daraja_webhook` function.

## 2. Background Queue Depth
**Metric**: `arq_queue_depth`
- **Threshold**: `> 100` jobs for more than `5m`.
- **Why**: The `arq` Redis queue normally processes jobs in milliseconds. A backlog of 100+ jobs means the `api-worker` container is either dead, failing to connect to the database, or the Mikrotik routers are hanging/timing out.
- **Action**: Check `api-worker` container logs. Verify connectivity to Redis and PostgreSQL.

## 3. Stuck Payment Reconciliation Backlog
**Metric**: `reconciliation_backlog_size`
- **Threshold**: `> 5` stuck payments for more than `10m`.
- **Why**: The `reconcile_payments_cron` runs every 5 minutes. If stuck payments (payments without vouchers) persist beyond 10 minutes, the automatic retry loop is failing repeatedly.
- **Action**: Manually check `payments` table for `status='confirmed'` without `vouchers`. Look at the worker logs for `generate_voucher_task` final attempt failures.

## 4. Router Connectivity (Heartbeat)
- **Threshold**: Any router failing heartbeat for `> 15m`.
- **Why**: If a Mikrotik router stops responding to REST API calls, no new customers can be provisioned on it, and active session syncing stops.
- **Action**: Verify the public IP of the router. Ensure the router is powered on and `zealnet-api` user has REST API access.
