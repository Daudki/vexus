"""
Shared pytest fixtures.

Each test gets a fresh in-memory SQLite database and a FastAPI
TestClient wired to it via dependency override — no test touches the
real dev/prod database.
"""
import os

# Settings.SECRET_KEY has no default (see app/config/settings.py) so
# that a real deployment fails loudly instead of silently running with
# a known, guessable key. That means the test suite must provide its
# own explicit, throwaway value -- this must happen before any `app.*`
# import below, since importing app.main/app.database.session
# transitively constructs Settings(). setdefault() so a developer's
# real .env (gitignored, not present in a fresh clone or CI) still
# takes precedence if one happens to exist locally.
os.environ.setdefault("SECRET_KEY", "test-only-secret-do-not-use-in-production")
os.environ.setdefault("AI_PROVIDER", "none")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.users.models import Role, RoleName

# Import all models so metadata is complete before create_all.
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


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    for role_name in RoleName:
        session.add(Role(name=role_name, description=role_name.value))
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    app.state.limiter.reset()  # rate-limit storage is process-global; isolate each test
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
