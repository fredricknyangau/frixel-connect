from contextlib import asynccontextmanager
import logging
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
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.packages.router import router as packages_router
from app.modules.payments.router import router as payments_router
from app.modules.vouchers.router import router as vouchers_router
from app.modules.sessions.router import router as sessions_router
from app.modules.webhooks.router import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await create_pool()
    yield
    await close_pool()


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade ISP billing API for the Kenyan market.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS Middleware Configuration ─────────────────────────────────────────────
# In development, we permit all origins (*) to simplify local UI integration.
# In production, we restrict cross-origin requests to a configurable domain list.
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
# Logs method, path, HTTP status, and duration of every request.
# WHY THIS BELONGS IN MIDDLEWARE AND NOT INDIVIDUAL ROUTE HANDLERS:
#   Writing logging inside individual endpoint functions results in duplicated
#   boilerplate and fails to record requests that are rejected early by Starlette
#   itself (such as 404 Not Found or 405 Method Not Allowed).
#   Middleware acts as a wrapper around the ASGI lifecycle, guaranteeing that
#   every incoming transaction is recorded uniformly.
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
# Catches unhandled runtime exceptions, outputs tracebacks to stderr, and returns
# a sanitised JSON payload.
# WHY WE CATCH THE BASE Exception CLASS:
#   FastAPI handles HTTPException and RequestValidationError with specific handlers.
#   By catching the raw base Exception, we intercept unexpected server crashes
#   (e.g., connection dropouts or database bugs) without blocking expected API responses
#   or validation errors (422) from bubbling up properly.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the full exception to the console with traceback
    logger.error(f"Global Error Handler caught unhandled error: {exc}", exc_info=exc)

    if settings.DEBUG:
        # Development mode: Expose full traceback details to assist troubleshooting
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred.",
                "error": str(exc),
                "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__),
            }
        )
    else:
        # Production mode: Output a generic message to prevent information leakage
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."}
        )


# ── Router registration ───────────────────────────────────────────────────────
# All routes live under /api/v1/
# Webhooks live at /api/v1/webhooks/ (Daraja needs a stable, public URL)

PREFIX = "/api/v1"

app.include_router(auth_router,      prefix=f"{PREFIX}/auth",     tags=["Auth"])
app.include_router(users_router,     prefix=f"{PREFIX}",          tags=["Users"])
app.include_router(packages_router,  prefix=f"{PREFIX}/packages", tags=["Packages"])
# Payments, vouchers, and sessions routers are mounted at the top-level PREFIX
# (not /payments, /vouchers, /sessions) because their routes span multiple
# path groups:
#   payments: /payments/stk, /payments/me  AND /reseller/payments, /admin/payments
#   vouchers: /vouchers/me, /vouchers/{id} AND /reseller/vouchers
#   sessions: /sessions/me                AND /admin/sessions
# Mounting at /api/v1 lets each router define its full path explicitly.
app.include_router(payments_router,  prefix=f"{PREFIX}",          tags=["Payments"])
app.include_router(vouchers_router,  prefix=f"{PREFIX}",          tags=["Vouchers"])
app.include_router(sessions_router,  prefix=f"{PREFIX}",          tags=["Sessions"])
app.include_router(webhooks_router,  prefix=f"{PREFIX}/webhooks", tags=["Webhooks"])


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }