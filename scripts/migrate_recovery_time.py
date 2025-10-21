"""Migration script to add recovery_time_hours column to database."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine


def migrate_recovery_time_column():
    """Add recovery_time_hours column to daily_metrics table."""
    print("🔄 Migrating database for Recovery Time tracking")
    print("=" * 60)

    # SQL statement to add recovery_time_hours column
    migration_sql = "ALTER TABLE daily_metrics ADD COLUMN recovery_time_hours INTEGER"

    with engine.connect() as conn:
        try:
            conn.execute(text(migration_sql))
            print("✅ Added column: recovery_time_hours")
            conn.commit()
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("⏭️  Column already exists: recovery_time_hours")
            else:
                print(f"❌ Error: {e}")
                raise

    print("=" * 60)
    print("✅ Recovery time migration complete!")
    print("\nNew column added:")
    print("  - recovery_time_hours (hours until ready for next quality workout)")
    print("\nThis metric is extracted from Garmin's training_status API")
    print("and helps the AI analyzer make better recovery recommendations.")


if __name__ == "__main__":
    migrate_recovery_time_column()
