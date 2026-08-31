"""Direct test of stale asset marking logic without full test infrastructure."""
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.assets.models import Asset, AssetStatus, AssetTrustStatus
from app.assets.service import DiscoveredHost
from app.discovery.service import DiscoveryService

# Import all models
from app.audit import models as _audit_models
from app.assets import models as _assets_models
from app.events import models as _events_models
from app.health import models as _health_models
from app.detection import models as _detection_models
from app.alerts import models as _alerts_models
from app.common import models as _common_models
from app.discovery import models as _discovery_models
from app.monitoring import models as _monitoring_models
from app.topology import models as _topology_models
from app.risk import models as _risk_models
from app.incidents import models as _incidents_models
from app.ai import models as _ai_models


def test_mark_missing_assets_offline():
    # Setup in-memory DB
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
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    # Create a stale asset
    stale = Asset(
        ip_address="10.0.0.10",
        hostname="stale-host",
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db.add(stale)
    db.commit()

    print(f"✓ Created stale asset at 10.0.0.10 with status {stale.status}")

    # Create a discovered host list (missing the stale IP)
    discovered_hosts = [
        DiscoveredHost(ip_address="10.0.0.11", mac_address="AA:BB:CC:DD:EE:11", hostname="live-host")
    ]

    # Create discovery service and call marking function
    from app.discovery.collectors import SimulatedCollector
    discovery = DiscoveryService(db, SimulatedCollector(discovered_hosts))
    
    now = datetime.now(timezone.utc)
    target_ranges = ["10.0.0.0/24"]
    
    discovery._mark_missing_assets_in_scan(discovered_hosts, target_ranges, now)

    # Check if stale asset is now marked offline
    refreshed = db.query(Asset).filter_by(ip_address="10.0.0.10").one()
    
    print(f"✓ After scan: stale asset status = {refreshed.status}")
    print(f"✓ Last seen = {refreshed.last_seen}")

    if refreshed.status == AssetStatus.OFFLINE:
        print("✅ TEST PASSED: Stale asset correctly marked OFFLINE")
        return True
    else:
        print(f"❌ TEST FAILED: Expected OFFLINE, got {refreshed.status}")
        return False

if __name__ == "__main__":
    import sys
    success = test_mark_missing_assets_offline()
    sys.exit(0 if success else 1)
