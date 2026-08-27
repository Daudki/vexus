from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text


class HealthService:
    def __init__(self, db: Session):
        self.db = db

    def check_health(self):
        try:
            self.db.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"

        return {
            "status": "healthy" if db_status == "healthy" else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": {"status": db_status},
            },
        }