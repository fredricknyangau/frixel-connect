from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import create_pool, close_pool

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