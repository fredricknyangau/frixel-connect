from prometheus_client import Counter, Gauge, Histogram

# HTTP Metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"]
)

# Webhook Metrics
webhook_events_total = Counter(
    "webhook_events_total",
    "Total webhook events processed",
    ["provider", "status"]
)

# Background Workers & Queues
arq_queue_depth = Gauge(
    "arq_queue_depth",
    "Current depth of the arq background task queue"
)

reconciliation_backlog_size = Gauge(
    "reconciliation_backlog_size",
    "Number of un-reconciled stuck payments"
)
