"""
Seed the four fixed roles (Admin, Security Analyst, Network Administrator,
Viewer) and, if none exists yet, one initial admin user from environment
variables (VEXUS_ADMIN_USERNAME / VEXUS_ADMIN_EMAIL / VEXUS_ADMIN_PASSWORD).

Run with: python -m scripts.seed
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.security import hash_password  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import SessionLocal, engine  # noqa: E402
from app.users.models import Role, RoleName, User  # noqa: E402

# Ensure model modules are imported so metadata is complete.
from app.audit import models as _audit_models  # noqa: F401,E402
from app.assets import models as _assets_models  # noqa: F401,E402
from app.events import models as _events_models  # noqa: F401,E402
from app.health import models as _health_models  # noqa: F401,E402
from app.detection import models as _detection_models  # noqa: F401,E402
from app.alerts import models as _alerts_models  # noqa: F401,E402
from app.common import models as _common_models  # noqa: F401,E402
from app.discovery import models as _discovery_models  # noqa: F401,E402
from app.monitoring import models as _monitoring_models  # noqa: F401,E402
from app.topology import models as _topology_models  # noqa: F401,E402
from app.risk import models as _risk_models  # noqa: F401,E402
from app.incidents import models as _incidents_models  # noqa: F401,E402
from app.ai import models as _ai_models  # noqa: F401,E402


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for role_name in RoleName:
            existing = db.query(Role).filter_by(name=role_name).first()
            if not existing:
                db.add(Role(name=role_name, description=role_name.value.replace("_", " ").title()))
        db.commit()

        admin_username = os.getenv("VEXUS_ADMIN_USERNAME")
        admin_email = os.getenv("VEXUS_ADMIN_EMAIL")
        admin_password = os.getenv("VEXUS_ADMIN_PASSWORD")

        if admin_username and admin_email and admin_password:
            if not db.query(User).filter_by(username=admin_username).first():
                admin_role = db.query(Role).filter_by(name=RoleName.ADMIN).first()
                db.add(
                    User(
                        username=admin_username,
                        email=admin_email,
                        password_hash=hash_password(admin_password),
                        role_id=admin_role.id,
                    )
                )
                db.commit()
                print(f"Created initial admin user '{admin_username}'.")
            else:
                print(f"Admin user '{admin_username}' already exists — skipping.")
        else:
            print(
                "VEXUS_ADMIN_USERNAME / VEXUS_ADMIN_EMAIL / VEXUS_ADMIN_PASSWORD not set — "
                "skipped initial admin creation. Roles were still seeded."
            )
    finally:
        db.close()


if __name__ == "__main__":
    run()
