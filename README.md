# AI-Powered Training Optimization System

An intelligent training assistant that analyzes Garmin fitness data using Claude AI to generate personalized daily workout recommendations. Prevents overtraining through smart load management and recovery tracking.

## ✅ Current Status (Phase 1 & Phase 2 Core - 2025-10-20)

**Production-Ready Features:**
- ✅ Garmin Connect integration with MFA support (token caching)
- ✅ **Phase 1 Enhanced Metrics** fully implemented:
  - Training Readiness Score (Garmin's AI readiness 0-100)
  - VO2 Max (cardiovascular fitness)
  - Training Status (PRODUCTIVE/MAINTAINING/PEAKING/STRAINED)
  - SPO2 (blood oxygen saturation)
  - Respiration Rate
- ✅ **Phase 2 AI Intelligence** (NEW - 2025-10-19):
  - **Activity type differentiation**: High/moderate/low impact classification
  - **Nuanced recovery recommendations**: Yoga-after-run vs run-after-run intelligence
  - **Multi-language support**: English and German recommendations
  - **Externalized prompts**: Easy threshold tuning via YAML config
- ✅ AI-powered daily readiness analysis (Claude Sonnet 4.5)
- ✅ **Recommendation-first dashboard** (NEW - 2025-10-20) with responsive design
- ✅ Historical baselines (30-day) with ACWR and trend analysis
- ✅ Scheduler job (Garmin sync + AI readiness) via APScheduler (cron-friendly)
- ✅ HRV baseline tracking and ACWR calculation

## Quick Start

### 1. Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
# Edit .env with your credentials:
# - GARMIN_EMAIL, GARMIN_PASSWORD
# - ANTHROPIC_API_KEY
# - User profile (age, gender, max HR, training goals)
# - SECRET_KEY (generate a strong value, do not leave blank)
# - Optional: LOG_LEVEL, LOG_DIR, SCHEDULER_HOUR, SCHEDULER_MINUTE
# - Optional: DATABASE_URL (set to your PostgreSQL DSN when deploying)
```

> ℹ️  If `DATABASE_URL` is omitted, the app defaults to `sqlite:///./data/training_data.db`. PostgreSQL deployments should provide a DSN such as `postgresql+psycopg://user:pass@host:5432/dbname`.

### 3. Initialize Database

```bash
python scripts/initial_setup.py
```

This command now applies Alembic migrations to the configured database. You can also run them manually with:

```bash
alembic upgrade head
```

### 4. First Sync (with MFA)

```bash
python scripts/sync_data.py --mfa-code 123456
# Subsequent syncs won't need MFA (tokens cached)
```

### 5. Run Application

```bash
# Terminal 1: Start web server
uvicorn app.main:app --reload --port 8002

# Terminal 2: Run scheduler worker (optional)
# Executes Garmin sync + readiness analysis at 08:00 local time (configurable).
python scripts/run_scheduler.py
```

### 6. Access Dashboard

Open http://localhost:8002/ in your browser to see:
- Today's AI recommendation
- Phase 1 Enhanced Recovery Metrics
- Training readiness score
- Suggested workout with rationale

## Running Tests

```bash
source .venv/bin/activate
PYTHONPATH=. pytest

# Example: focus on readiness suite
PYTHONPATH=. pytest -k readiness
```

## Key Features

### Daily AI Analysis
- Analyzes HRV, sleep, resting HR, training load, stress, body battery
- **NEW**: Integrates Garmin Training Readiness, VO2 Max, Training Status, SPO2, Respiration
- **Activity Type Intelligence**: Differentiates between high/moderate/low impact activities
  - High Impact: Intense runs, cycling, training effect ≥3.0, HR zones 4-5 >70%, or >90min duration
  - Moderate Impact: Mixed intensity workouts, training effect 2.5-3.0
  - Low Impact: Yoga, stretching, recovery activities, training effect <2.5
- **Nuanced Recovery**: Recommends yoga after hard run, but flags run-after-run risks
- Provides personalized recommendation: rest/easy/moderate/high_intensity
- Explains reasoning and flags overtraining risks
- **Multi-language**: Full recommendations in English or German (configurable)

### Smart Recovery Tracking
- 30-day HRV baseline calculation
- Acute:Chronic Workload Ratio (ACWR) monitoring
- Consecutive training day tracking
- Sleep debt analysis

### Automated Workflow
- Automated daily sync/analysis (scheduler worker or cron, default 08:00 local time)
- Token-based authentication (MFA only needed once)
- Graceful error handling and retry logic

## Documentation

- **Full Specification**: `AI_Training_Optimizer_Specification.md`
- **Project Instructions (for AI)**: `CLAUDE.md`
- **Repository Guidelines**: `AGENTS.md`
- **Garmin API Data**: `GARMIN_API_DATA_AVAILABLE.md`
- **Daily Sync Setup**: `DAILY_SYNC_SETUP.md`
- **Historical Backfill**: `HISTORICAL_DATA_SETUP.md`
- **Architecture Backlog**: `docs/architecture_backlog.md`
- **Logging Configuration**: Set `LOG_LEVEL`/`LOG_DIR` in `.env`; runtime logs write to `logs/app.log` and component-specific files.
- **Prompt Templates**: Adjust `app/config/prompts.yaml` and `app/prompts/` to customize Claude prompt wording and thresholds.

## Tech Stack

- **Python 3.10+** with FastAPI
- **garminconnect 0.2.30** - Garmin API client
- **Anthropic Claude API** (claude-sonnet-4-5-20250929) with multi-language support (EN/DE)
- **SQLAlchemy** with SQLite (PostgreSQL ready)
- **APScheduler** for automated syncing
- **YAML-based configuration** for AI prompts, thresholds, and localization

## Common Commands

```bash
# Manual sync with today + yesterday's data
curl -X POST http://localhost:8002/manual/sync/now

# Get today's AI recommendation
curl http://localhost:8002/api/recommendations/today | python3 -m json.tool

# Backfill historical data (90 days)
python scripts/sync_data.py --date 2025-01-01 --force

# Run scheduler job immediately (testing)
python scripts/run_scheduler.py --run-now
```

## Configuration & Customization

### AI Prompt Configuration (`app/config/prompts.yaml`)

The system uses externalized configuration for easy tuning without code changes:

- **Thresholds**: HRV drops, ACWR limits, readiness score ranges
- **Activity Classification**: Training effect thresholds, HR zone thresholds, duration rules
- **Localization**: Default language and translations (EN/DE)
- **Prompt Templates**: Located in `app/prompts/` directory

**Example customization:**
```yaml
thresholds:
  hrv_drop_pct: 10        # Alert if HRV drops >10% from baseline
  acwr_high: 1.5          # Flag high injury risk at ACWR >1.5
  readiness:
    critical: 20          # 0-20 = rest day required
    moderate: 75          # 76-100 = high intensity OK

default_language: de      # Change to German output
```

See `app/config/prompts.yaml` for all configurable parameters.

## Phase 1 Enhanced Metrics

The system now tracks and analyzes advanced Garmin metrics:

| Metric | Purpose | AI Usage |
|--------|---------|----------|
| **Training Readiness** | Garmin's AI readiness score (0-100) | Primary decision driver for rest days |
| **VO2 Max** | Cardiovascular fitness level | Contextualizes training capacity |
| **Training Status** | PRODUCTIVE/MAINTAINING/etc | Reassures effectiveness of training |
| **SPO2** | Blood oxygen saturation | Recovery and health indicator |
| **Respiration** | Breathing rate | Stress/illness/overtraining detector |

## Next Steps (Phase 2+)

- Training plan generation with periodization
- Interactive charts and trends visualization
- AI chat interface for training questions
- Email/SMS notifications

Refer to `CLAUDE.md` for detailed implementation status and architecture.
