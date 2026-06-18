from contextlib import asynccontextmanager
import logging
import asyncio
import time
import traceback

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import create_pool, close_pool
from app.core.redis import init_redis, close_redis

import structlog
import uuid
from structlog.contextvars import bind_contextvars, clear_contextvars
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

from app.core.logging import setup_logging
from app.core.metrics import http_requests_total, http_request_duration_seconds

# Set up structured logging based on environment
setup_logging(json_logs=settings.APP_ENV == "production")
logger = structlog.get_logger(__name__)

# Module routers — imported here, registered below
from app.modules.auth.router     import router as auth_router
from app.modules.users.router    import router as users_router
from app.modules.packages.router import router as packages_router
from app.modules.payments.router import router as payments_router
from app.modules.vouchers.router import router as vouchers_router
from app.modules.sessions.router import router as sessions_router
from app.modules.webhooks.router import router as webhooks_router
from app.modules.tenants.router  import router as tenants_router   # Phase 1
from app.modules.routers.router  import router as routers_router    # Phase 2
from app.modules.routers.service import router_heartbeat_loop       # Phase 2
from app.modules.wallets.router  import router as wallets_router    # Phase 4
from app.modules.subscriptions.router import router as subscriptions_router # Phase 6
from app.modules.invoices.router import router as invoices_router # Phase 6


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Initialize DB connection pool
    await create_pool()

    # Initialize shared Redis connection pool for background task workers
    await init_redis()
    
    # Phase 2: Start background heartbeat checks for all registered routers
    heartbeat_task = asyncio.create_task(router_heartbeat_loop())
    
    yield
    
    # Shutdown sequence
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    await close_redis()
    await close_pool()


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade multi-tenant ISP billing platform.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS Middleware ───────────────────────────────────────────────────────────
if settings.APP_ENV == "production":
    origins = settings.ALLOWED_ORIGINS
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    clear_contextvars()
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    bind_contextvars(request_id=request_id)
    
    # Optional: we can bind tenant_id later in the request lifecycle if auth extracts it,
    # but request_id is always available from the start.

    start_time = time.perf_counter()
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        process_time = time.perf_counter() - start_time
        
        # Log structured format
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=round(process_time * 1000, 2)
        )
        
        # Metrics (group paths to avoid high cardinality in a real system, but raw path is fine for MLP)
        http_requests_total.labels(
            method=request.method,
            path=request.url.path,
            status_code=status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=request.method,
            path=request.url.path
        ).observe(process_time)


# ── Global Exception Handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=exc)

    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred.",
                "error": str(exc),
                "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__),
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."}
        )


# ── Router registration ───────────────────────────────────────────────────────
PREFIX = "/api/v1"

app.include_router(tenants_router,  prefix=f"{PREFIX}/tenants",  tags=["Tenants"])   # Phase 1
app.include_router(routers_router,  prefix=f"{PREFIX}/admin/routers", tags=["Routers"])   # Phase 2
app.include_router(auth_router,     prefix=f"{PREFIX}/auth",      tags=["Auth"])
app.include_router(users_router,    prefix=f"{PREFIX}",           tags=["Users"])
app.include_router(packages_router, prefix=f"{PREFIX}/packages",  tags=["Packages"])
app.include_router(payments_router, prefix=f"{PREFIX}",           tags=["Payments"])
app.include_router(vouchers_router, prefix=f"{PREFIX}",           tags=["Vouchers"])
app.include_router(sessions_router, prefix=f"{PREFIX}",           tags=["Sessions"])
app.include_router(webhooks_router, prefix=f"{PREFIX}/webhooks",  tags=["Webhooks"])
app.include_router(wallets_router,  prefix=f"{PREFIX}",           tags=["Wallets"])    # Phase 4
app.include_router(subscriptions_router, prefix=f"{PREFIX}",      tags=["Subscriptions"]) # Phase 6
app.include_router(invoices_router, prefix=f"{PREFIX}",           tags=["Invoices"]) # Phase 7


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "2.0.0",
    }


# ── Metrics ───────────────────────────────────────────────────────────────────
@app.get("/metrics", tags=["Observability"])
async def get_metrics():
    """Exposes Prometheus metrics for scraping."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)