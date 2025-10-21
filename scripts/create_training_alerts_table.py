#!/usr/bin/env python3
"""Create training_alerts table migration script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import get_settings
from app.models.database_models import TrainingAlert


def create_training_alerts_table():
    """Create training_alerts table with all indexes and constraints."""
    settings = get_settings()
    engine = create_engine(settings.database_url)

    print("Creating training_alerts table...")

    # Enable foreign key enforcement for SQLite
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()

    # Create table using SQLAlchemy metadata
    TrainingAlert.__table__.create(engine, checkfirst=True)

    print("✅ Table created successfully!")

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='training_alerts'"
        ))
        if result.fetchone():
            print("✅ Verification passed")
        else:
            print("❌ ERROR: Table creation failed")
            return False

    return True


if __name__ == "__main__":
    success = create_training_alerts_table()
    sys.exit(0 if success else 1)
