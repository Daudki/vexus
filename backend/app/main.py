from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth.router import router as auth_router, limiter as auth_limiter
from app.config.settings import get_settings
from app.database.base import Base
from app.database.session import engine
from app.health.router import router as health_router
from app.users.router import router as users_router
from app.assets.router import router as assets_router
from app.discovery.router import router as discovery_router
from app.monitoring.router import router as monitoring_router
from app.topology.router import router as topology_router
from app.detection.router import router as detection_router
from app.alerts.router import router as alerts_router
from app.risk.router import router as risk_router
from app.incidents.router import router as incidents_router
from app.ai.router import router as ai_router
from app.audit.router import router as audit_router
from app.admin.router import router as admin_router
from app.sense.router import router as sense_router
from app.correlation.router import router as correlation_router

# Import all models so Base.metadata is aware of every table before
# create_all runs. (Alembic migrations take over for anything beyond
# local dev — see alembic/.)
from app.users import models as _users_models  # noqa: F401
from app.audit import models as _audit_models  # noqa: F401
from app.assets import models as _assets_models  # noqa: F401
from app.events import models as _events_models  # noqa: F401
from app.health import models as _health_models  # noqa: F401
from app.detection import models as _detection_models  # noqa: F401
from app.alerts import models as _alerts_models  # noqa: F401
from app.common import models as _common_models  # noqa: F401
from app.discovery import models as _discovery_models  # noqa: F401
from app.monitoring import models as _monitoring_models  # noqa: F401
from app.topology import models as _topology_models  # noqa: F401
from app.risk import models as _risk_models  # noqa: F401
from app.incidents import models as _incidents_models  # noqa: F401
from app.ai import models as _ai_models  # noqa: F401
from app.sense import models as _sense_models  # noqa: F401


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="VEXUS API",
        description="AI-Powered Network Security Intelligence Platform",
        version="0.1.0",
    )

    # Rate limiting
    app.state.limiter = auth_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(assets_router)
    app.include_router(discovery_router)
    app.include_router(monitoring_router)
    app.include_router(topology_router)
    app.include_router(detection_router)
    app.include_router(alerts_router)
    app.include_router(risk_router)
    app.include_router(incidents_router)
    app.include_router(ai_router)
    app.include_router(audit_router)
    app.include_router(admin_router)
    app.include_router(sense_router)
    app.include_router(correlation_router)

    if settings.APP_ENV == "development":
        # Local convenience only. Production uses Alembic migrations —
        # see alembic/ and docs/development/setup.md.
        Base.metadata.create_all(bind=engine)

    return app


app = create_app()


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if get_settings().APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response