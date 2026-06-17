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

# Set up logging for main app module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module routers — imported here, registered below
from app.modules.auth.router     import router as auth_router
from app.modules.users.router    import router as users_router
from app.modules.packages.router import router as packages_router
from app.modules.payments.router import router as payments_router
from app.modules.vouchers.router import router as vouchers_router
from app.modules.vouchers.service import provision_retry_poller
from app.modules.sessions.router import router as sessions_router
from app.modules.webhooks.router import router as webhooks_router
from app.modules.tenants.router  import router as tenants_router   # Phase 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await create_pool()
    # Phase 3 replaces this poller with a durable arq worker.
    # Until then the in-process poller provides basic self-healing.
    poller_task = asyncio.create_task(provision_retry_poller())
    yield
    poller_task.cancel()
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


# ── Request Logging Middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    logger.info(
        f"{request.method} {request.url.path} {response.status_code} {process_time:.0f}ms"
    )
    return response


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

app.include_router(tenants_router,  prefix=f"{PREFIX}/tenants",  tags=["Tenants"])   # Phase 1 — NEW
app.include_router(auth_router,     prefix=f"{PREFIX}/auth",      tags=["Auth"])
app.include_router(users_router,    prefix=f"{PREFIX}",           tags=["Users"])
app.include_router(packages_router, prefix=f"{PREFIX}/packages",  tags=["Packages"])
app.include_router(payments_router, prefix=f"{PREFIX}",           tags=["Payments"])
app.include_router(vouchers_router, prefix=f"{PREFIX}",           tags=["Vouchers"])
app.include_router(sessions_router, prefix=f"{PREFIX}",           tags=["Sessions"])
app.include_router(webhooks_router, prefix=f"{PREFIX}/webhooks",  tags=["Webhooks"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "2.0.0",
    }