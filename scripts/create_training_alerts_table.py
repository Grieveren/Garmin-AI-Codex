#!/usr/bin/env python3
"""Create training_alerts table migration script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from app.config import get_settings
from app.models.database_models import TrainingAlert


def rollback_training_alerts_table():
    """Rollback: Drop training_alerts table and all associated indexes."""
    settings = get_settings()
    engine = create_engine(settings.database_url)

    print("Rolling back training_alerts table...")

    try:
        with engine.connect() as conn:
            # Enable foreign key enforcement
            conn.execute(text("PRAGMA foreign_keys=ON"))

            # Drop table (cascades to indexes in SQLite)
            conn.execute(text("DROP TABLE IF EXISTS training_alerts"))
            conn.commit()

        print("✅ Rollback completed successfully!")
        return True
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False


def verify_table_structure():
    """Verify table structure matches expected schema."""
    settings = get_settings()
    engine = create_engine(settings.database_url)

    inspector = inspect(engine)

    # Check table exists
    if 'training_alerts' not in inspector.get_table_names():
        print("❌ Table 'training_alerts' does not exist")
        return False

    # Check columns
    columns = {col['name']: col for col in inspector.get_columns('training_alerts')}
    expected_columns = {
        'id', 'alert_type', 'severity', 'title', 'message', 'recommendation',
        'trigger_date', 'trigger_metrics', 'status', 'acknowledged_at',
        'resolved_at', 'created_at', 'updated_at'
    }

    missing_columns = expected_columns - set(columns.keys())
    if missing_columns:
        print(f"❌ Missing columns: {missing_columns}")
        return False

    # Check indexes
    indexes = inspector.get_indexes('training_alerts')
    index_names = {idx['name'] for idx in indexes}

    expected_indexes = {
        'ix_training_alerts_alert_type',
        'ix_training_alerts_severity',
        'ix_training_alerts_trigger_date',
        'ix_training_alerts_status',
        'ix_training_alerts_active_recent',
        'ix_training_alerts_unique_active'
    }

    missing_indexes = expected_indexes - index_names
    if missing_indexes:
        print(f"❌ Missing indexes: {missing_indexes}")
        return False

    print("✅ Table structure verification passed")
    return True


def create_training_alerts_table():
    """Create training_alerts table with all indexes and constraints."""
    settings = get_settings()
    engine = create_engine(settings.database_url)

    print("Creating training_alerts table...")

    try:
        # Enable foreign key enforcement for SQLite
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

        # Create table using SQLAlchemy metadata
        TrainingAlert.__table__.create(engine, checkfirst=True)

        print("✅ Table created successfully!")

        # Comprehensive verification
        if not verify_table_structure():
            print("❌ Migration failed verification - rolling back")
            rollback_training_alerts_table()
            return False

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("Attempting rollback...")
        rollback_training_alerts_table()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Manage training_alerts table migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback (drop) the table')
    args = parser.parse_args()

    if args.rollback:
        success = rollback_training_alerts_table()
    else:
        success = create_training_alerts_table()

    sys.exit(0 if success else 1)
