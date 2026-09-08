"""
Seed the four fixed roles (Admin, Security Analyst, Network Administrator,
Viewer) and, if none exists yet, one initial admin user from environment
variables (VEXUS_ADMIN_USERNAME / VEXUS_ADMIN_EMAIL / VEXUS_ADMIN_PASSWORD).

Run with: python -m scripts.seed
"""
import os
import sys
import secrets

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
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Create all roles first
        roles_created = []
        for role_name in RoleName:
            existing = db.query(Role).filter_by(name=role_name).first()
            if not existing:
                role = Role(name=role_name, description=role_name.value.replace("_", " ").title())
                db.add(role)
                roles_created.append(role_name.value)
                print(f"✅ Created role: {role_name.value}")
            else:
                print(f"ℹ️ Role already exists: {role_name.value}")
        
        # IMPORTANT: Commit roles BEFORE creating user
        db.commit()
        print(f"\n✅ Roles committed to database")

        # 2. Get admin role (must exist now)
        admin_role = db.query(Role).filter_by(name=RoleName.ADMIN).first()
        if not admin_role:
            print("❌ ERROR: Admin role not found after creation!")
            return

        print(f"✅ Admin role ID: {admin_role.id}")

        # 3. Create admin user
        admin_username = os.getenv("VEXUS_ADMIN_USERNAME")
        admin_email = os.getenv("VEXUS_ADMIN_EMAIL")
        admin_password = os.getenv("VEXUS_ADMIN_PASSWORD")

        # Check if user exists
        existing_user = db.query(User).filter_by(username=admin_username).first()

        if existing_user:
            print(f"ℹ️ Admin user '{admin_username}' already exists.")
            # Ensure role is correct
            if existing_user.role_id != admin_role.id:
                existing_user.role_id = admin_role.id
                db.commit()
                print(f"✅ Updated role for {admin_username} to ADMIN")
            else:
                print(f"ℹ️ Role already correct for {admin_username}")
        else:
            if not admin_password:
                # No hardcoded fallback: shipping a known default password
                # in a security product is itself a vulnerability. Generate
                # a random one so a forgotten env var fails safe instead of
                # producing a predictable admin account.
                admin_password = secrets.token_urlsafe(16)
                print(
                    "⚠️  VEXUS_ADMIN_PASSWORD was not set. Generated a random "
                    "password for this admin account (shown once below) — "
                    "set VEXUS_ADMIN_PASSWORD explicitly to control it yourself."
                )

            # Create new admin user
            user = User(
                username=admin_username,
                email=admin_email,
                password_hash=hash_password(admin_password),
                role_id=admin_role.id,
                is_active=True,
            )
            db.add(user)
            db.commit()
            print(f"✅ Created admin user: {admin_username}")

        # 4. Verify
        verify_user = db.query(User).filter_by(username=admin_username).first()
        if verify_user:
            print(f"\n📋 Verification:")
            print(f"  - Username: {verify_user.username}")
            print(f"  - Email: {verify_user.email}")
            print(f"  - Role ID: {verify_user.role_id}")
            print(f"  - Role Name: {verify_user.role.name.value if verify_user.role else 'NO ROLE!'}")
            print(f"  - Is Active: {verify_user.is_active}")
            print(f"\n🎉 Seeding complete!")
            print(f"Login: {admin_username} / {admin_password}")
        else:
            print("❌ Failed to verify user creation!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    run()