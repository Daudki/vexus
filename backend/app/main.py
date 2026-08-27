"""
VEXUS backend entrypoint.

Application-factory pattern: each domain module owns its own APIRouter
and is registered here. Routers contain no business logic — see each
module's service.py for that.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth.router import router as auth_router
from app.config.settings import get_settings
from app.database.base import Base
from app.database.session import engine
from app.health.router import router as health_router  # ADD THIS

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


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="VEXUS API",
        description="AI-Powered Network Security Intelligence Platform",
        version="0.1.0",
    )

    # Rate limiting - remove this if auth.router doesn't have limiter yet
    # app.state.limiter = auth_limiter
    # app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)      # ✅ Health router
    app.include_router(auth_router)        # ✅ Auth router
    # app.include_router(users_router)     # Uncomment when users router exists
    # app.include_router(assets_router)    # Uncomment when assets router exists
    # app.include_router(discovery_router)
    # app.include_router(monitoring_router)
    # app.include_router(topology_router)
    # app.include_router(detection_router)
    # app.include_router(alerts_router)
    # app.include_router(risk_router)
    # app.include_router(incidents_router)
    # app.include_router(ai_router)

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