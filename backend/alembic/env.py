"""
Alembic environment.

The actual database URL always comes from app settings (i.e.
DATABASE_URL in .env), never from alembic.ini directly — this keeps
one source of truth for connection config between the app and its
migrations.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import get_settings  # noqa: E402
from app.database.base import Base  # noqa: E402

# Import every domain's models so autogenerate sees the full schema.
from app.users import models as _users_models  # noqa: F401,E402
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

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
