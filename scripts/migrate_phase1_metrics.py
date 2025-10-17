"""Migration script to add Phase 1 enhanced metrics to database."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine

def migrate_phase1_columns():
    """Add Phase 1 enhanced metric columns to daily_metrics table."""
    print("🔄 Migrating database for Phase 1 Enhanced Metrics")
    print("=" * 60)

    # SQL statements to add new columns
    migrations = [
        # Training Readiness & Performance
        "ALTER TABLE daily_metrics ADD COLUMN training_readiness_score INTEGER",
        "ALTER TABLE daily_metrics ADD COLUMN vo2_max REAL",
        "ALTER TABLE daily_metrics ADD COLUMN training_status VARCHAR(50)",

        # Advanced Health Metrics
        "ALTER TABLE daily_metrics ADD COLUMN spo2_avg REAL",
        "ALTER TABLE daily_metrics ADD COLUMN spo2_min REAL",
        "ALTER TABLE daily_metrics ADD COLUMN respiration_avg REAL",
    ]

    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                column_name = sql.split("ADD COLUMN ")[1].split()[0]
                print(f"✅ Added column: {column_name}")
                conn.commit()
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    column_name = sql.split("ADD COLUMN ")[1].split()[0]
                    print(f"⏭️  Column already exists: {column_name}")
                else:
                    print(f"❌ Error: {e}")
                    raise

    print("=" * 60)
    print("✅ Phase 1 migration complete!")
    print("\nNew columns added:")
    print("  - training_readiness_score (Garmin's AI readiness 0-100)")
    print("  - vo2_max (ml/kg/min)")
    print("  - training_status (productive/maintaining/peaking/etc)")
    print("  - spo2_avg (blood oxygen %)")
    print("  - spo2_min (blood oxygen % minimum)")
    print("  - respiration_avg (breaths per minute)")

if __name__ == "__main__":
    migrate_phase1_columns()
