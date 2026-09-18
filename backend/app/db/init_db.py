from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.core.config import settings
import app.models # Ensure all models are registered with Base metadata
from seed.dev_seed import seed_database

def init_db():
    """Create all database tables and seed with development data if configured."""
    print(f"[DB] Initializing database with engine: {engine.url}")
    Base.metadata.create_all(bind=engine)
    
    if settings.AUTO_SEED:
        db = SessionLocal()
        try:
            seed_database(db)
        finally:
            db.close()
