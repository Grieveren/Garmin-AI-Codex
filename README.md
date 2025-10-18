# AI-Powered Training Optimization System

An intelligent training assistant that analyzes Garmin fitness data using Claude AI to generate personalized daily workout recommendations. Prevents overtraining through smart load management and recovery tracking.

## ✅ Current Status (Phase 1 Complete - 2025-10-17)

**Production-Ready Features:**
- ✅ Garmin Connect integration with MFA support (token caching)
- ✅ **Phase 1 Enhanced Metrics** fully implemented:
  - Training Readiness Score (Garmin's AI readiness 0-100)
  - VO2 Max (cardiovascular fitness)
  - Training Status (PRODUCTIVE/MAINTAINING/PEAKING/STRAINED)
  - SPO2 (blood oxygen saturation)
  - Respiration Rate
- ✅ AI-powered daily readiness analysis (Claude Sonnet 4.5)
- ✅ Web dashboard with today's recommendation
- ✅ Automated daily sync (7 AM) with 90 days of historical data
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
```

### 3. Initialize Database

```bash
python scripts/initial_setup.py
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

# Terminal 2: Start scheduler (optional - for automated sync)
python scripts/run_scheduler.py
```

### 6. Access Dashboard

Open http://localhost:8002/dashboard in your browser to see:
- Today's AI recommendation
- Phase 1 Enhanced Recovery Metrics
- Training readiness score
- Suggested workout with rationale

## Key Features

### Daily AI Analysis
- Analyzes HRV, sleep, resting HR, training load, stress, body battery
- **NEW**: Integrates Garmin Training Readiness, VO2 Max, Training Status, SPO2, Respiration
- Provides personalized recommendation: rest/easy/moderate/high_intensity
- Explains reasoning and flags overtraining risks

### Smart Recovery Tracking
- 30-day HRV baseline calculation
- Acute:Chronic Workload Ratio (ACWR) monitoring
- Consecutive training day tracking
- Sleep debt analysis

### Automated Workflow
- Daily sync at 7 AM (configurable)
- Token-based authentication (MFA only needed once)
- Graceful error handling and retry logic

## Documentation

- **Full Specification**: `AI_Training_Optimizer_Specification.md`
- **Project Instructions (for AI)**: `CLAUDE.md`
- **Repository Guidelines**: `AGENTS.md`
- **Garmin API Data**: `GARMIN_API_DATA_AVAILABLE.md`
- **Daily Sync Setup**: `DAILY_SYNC_SETUP.md`
- **Historical Backfill**: `HISTORICAL_DATA_SETUP.md`

## Tech Stack

- **Python 3.10+** with FastAPI
- **garminconnect 0.2.26** - Garmin API client
- **Anthropic Claude API** (claude-sonnet-4-5-20250929)
- **SQLAlchemy** with SQLite (PostgreSQL ready)
- **APScheduler** for automated syncing

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
