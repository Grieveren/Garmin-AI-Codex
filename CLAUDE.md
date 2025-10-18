# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Powered Training Optimization System that fetches Garmin fitness data, analyzes it using Claude AI, and generates adaptive daily workout recommendations. The system prevents overtraining through intelligent load management and provides personalized coaching based on recovery metrics (HRV, sleep, resting HR).

## Tech Stack

- **Python 3.10+** with FastAPI
- **garminconnect** - Unofficial Garmin API client (may break if Garmin updates)
- **Anthropic Claude API** (claude-sonnet-4-5-20250929) for AI analysis
- **SQLAlchemy** with SQLite (upgradeable to PostgreSQL)
- **APScheduler** for automated daily syncing
- **Pydantic Settings** for configuration management

## Common Development Commands

### Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Configure with your credentials
```

### Running the Application
```bash
# Start the FastAPI server
uvicorn app.main:app --reload

# Run the scheduler process (separate terminal)
python scripts/run_scheduler.py

# Run scheduler job immediately for testing
python scripts/run_scheduler.py --run-now

# Manual data sync from Garmin
python scripts/sync_data.py --mfa-code 123456
```

### Docker Deployment
```bash
# Run both app and scheduler
docker-compose up

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_garmin_service.py

# Run with verbose output
pytest -v
```

### Database Operations
```bash
# Initialize database schema
python scripts/initial_setup.py

# Backfill historical data
python scripts/backfill_data.py --days 90
```

## Architecture

### Core Service Layer (`app/services/`)

**GarminService** - Handles all Garmin Connect API interactions with MFA token caching:
- Token-based authentication with persistent storage (`.garmin_tokens`)
- Handles MFA authentication flow (user provides 6-digit code)
- Gracefully degrades when profile API calls fail but OAuth succeeds
- Critical: `garminconnect` library is unofficial and may break with Garmin API changes

**AIAnalyzer** - Claude AI integration for workout analysis:
- Daily readiness analysis based on sleep, HRV, resting HR, training load
- Workout recommendations (high_intensity, moderate, easy, rest)
- Training plan adaptation based on recovery metrics
- Uses comprehensive prompt engineering with user profile, physiological data, and training history

**TrainingPlanner** - Generates and adapts training plans:
- Periodized plans (base, build, peak, taper phases)
- Dynamic adaptation based on daily readiness scores
- Workout library with structured progressions

**DataProcessor** - Aggregates and prepares data for AI analysis:
- Calculates acute/chronic workload ratios (ACWR)
- HRV baseline tracking (7-day, 30-day)
- Training load metrics (fitness, fatigue, form)

**NotificationService** - Sends daily recommendations:
- Email/SMS notifications with workout suggestions
- Alert triggers for overtraining and illness detection

### Database Models (`app/models/database_models.py`)

Key tables (refer to AI_Training_Optimizer_Specification.md for full schema):
- `daily_metrics` - Steps, HR, HRV, sleep, body battery
- `sleep_sessions` - Detailed sleep stage data
- `activities` - Garmin workouts with training effect/load
- `daily_readiness` - AI-generated readiness scores and recommendations
- `training_plans` / `planned_workouts` - Structured training programs
- `training_load_tracking` - ACWR, fitness/fatigue/form
- `ai_analysis_cache` - Cached AI responses to reduce API costs

### Configuration (`app/config.py`)

Uses Pydantic Settings with `.env` file support:
- Garmin credentials and token storage path
- Anthropic API key
- Database URL (SQLite default, PostgreSQL for production)
- Scheduling parameters (sync time, timezone)
- User profile (age, gender, HR zones, training goals)
- AI model settings (model name, cache duration, token limits)

### Scheduler Design (`scripts/run_scheduler.py`)

- Uses `filelock` to prevent multiple instances
- Runs as standalone process (not embedded in FastAPI)
- Daily job at 8 AM: sync Garmin data → AI analysis → send notification
- `--run-now` flag for immediate execution during development

## Implementation Status & Phases

**Phase 1 (Foundation & Enhanced Metrics) - ✅ COMPLETE (2025-10-17):**
- ✅ Project structure created
- ✅ Garmin authentication with MFA support (token caching working)
- ✅ Full database models with Phase 1 Enhanced Metrics
- ✅ Complete data sync implementation (scripts/sync_data.py, app/routers/manual_sync.py)
- ✅ **Phase 1 Enhanced Metrics Fully Implemented:**
  - Training Readiness Score (Garmin's AI readiness 0-100)
  - VO2 Max (cardiovascular fitness ml/kg/min)
  - Training Status (PRODUCTIVE/MAINTAINING/PEAKING/STRAINED/OVERREACHING)
  - SPO2 (blood oxygen saturation %)
  - Respiration Rate (breaths per minute)
- ✅ 90 days of historical data backfilled
- ✅ Dashboard displaying all Phase 1 metrics with graceful degradation
- ✅ API endpoints: health check, manual sync (/manual/sync/now), recommendations (/api/recommendations/today)

**Phase 2 (AI Engine) - ✅ COMPLETE (Core Features):**
- ✅ **Daily readiness analysis (PRODUCTION READY)**
  - Comprehensive AI analysis using Claude Sonnet 4.5
  - Integrates all Phase 1 Enhanced Metrics
  - HRV baseline tracking (7-day, 30-day)
  - ACWR (Acute:Chronic Workload Ratio) calculation
  - Consecutive training day tracking
  - Personalized recommendations: high_intensity/moderate/easy/rest
- ✅ **Prompt engineering complete**
  - Detailed Phase 1 metrics usage guidelines
  - Training Status contextualization
  - VO2 Max fitness level interpretation
  - SPO2 and Respiration assessment criteria
- ⚠️ Training plan generation (backlog)
- ⚠️ Plan adaptation based on recovery metrics (backlog)

**Phase 3 (Web Interface) - 🟡 PARTIAL:**
- ✅ **Dashboard showing today's recommendation** (dashboard.html)
- ✅ **Phase 1 Enhanced Recovery Metrics card** (with graceful degradation)
- ✅ Manual sync UI with MFA code entry
- ⚠️ Training plan visualization (not started)
- ⚠️ AI chat interface with streaming responses (not started)
- ⚠️ Interactive charts (Plotly/Dash) (not started)

**Phase 4 (Automation) - 🟡 PARTIAL:**
- ✅ Scheduler infrastructure with locking (scripts/run_scheduler.py)
- ✅ **Daily sync job (FULLY WORKING)** - runs at 7 AM with Phase 1 metrics
- ⚠️ Email/SMS notifications (not implemented)

## Critical Considerations

### Garmin API Reliability ✅ WORKING (Updated 2025-10-17)
The `garminconnect` library reverse-engineers Garmin's web API and is NOT officially supported.

**CURRENT STATUS (2025-10-17)**:
- ✅ **Version**: garminconnect==0.2.26 (Python 3.14 compatible)
- ✅ **Authentication**: MFA flow working, tokens cached in `.garmin_tokens/`
- ✅ **Data Retrieval**: ALL critical endpoints working (see GARMIN_API_DATA_AVAILABLE.md)
- ⚠️ **Version 0.2.30**: Has Python 3.14 compatibility issues (type annotation bugs)
- ✅ **Data Available**: Steps, HR, HRV, sleep, activities, stress, body battery, SPO2, respiration, hydration, training status, and more

**Key Findings**:
- 72 GET methods available in garminconnect
- Most reliable methods: `get_stats()`, `get_heart_rates()`, `get_sleep_data()`, `get_activities()`
- `get_user_summary()` works in 0.2.26 (was broken in 0.2.17)
- Tokens cache successfully and work without MFA for extended periods

If Garmin updates their API:
1. Check GitHub issues: https://github.com/cyberjunky/python-garminconnect
2. Look for updated versions or community forks
3. Test with `python3 -m scripts.sync_data --mfa-code CODE`
4. Fallback: Manual FIT file import via `scripts/import_fit_files.py` (backlog)

### MFA Authentication Flow
- First login requires 6-digit code: `python scripts/sync_data.py --mfa-code 123456`
- Tokens cached in `.garmin_tokens` for subsequent logins
- If token cache corrupted, delete file and re-authenticate

### AI Analysis Costs
- Daily analysis: ~$0.10-0.20/day
- Estimated $5-15/month for regular use
- Uses prompt caching to reduce costs
- Cache AI responses in `ai_analysis_cache` table (24 hour TTL)

### Training Load Calculations
**Acute:Chronic Workload Ratio (ACWR):**
- Optimal range: 0.8-1.3
- >1.5 indicates injury risk
- Used to prevent overtraining and guide weekly volume

**Fitness/Fatigue/Form Model:**
- Fitness = 42-day exponential weighted moving average
- Fatigue = 7-day exponential weighted moving average
- Form = Fitness - Fatigue (positive = fresh, negative = fatigued)

### Scheduler Deployment
- Only ONE scheduler instance should run (enforced via filelock)
- In production: Use systemd service, Docker container, or cloud scheduler
- Separate from web app to ensure reliability
- Lock file `.scheduler.lock` prevents concurrent runs

## API Endpoints

**System:**
- `GET /health` - Health check

**Data Sync:**
- `POST /api/sync/manual` - Trigger manual Garmin sync

**Recommendations (when implemented):**
- `GET /api/recommendations/today` - Today's AI-generated workout
- `POST /api/recommendations/adapt-plan` - Modify plan based on readiness

**Training Plans (when implemented):**
- `GET /api/training/plans/current` - Active training plan
- `POST /api/training/plans` - Generate new plan
- `PUT /api/training/plans/{id}/workouts/{id}` - Mark workout complete

**AI Chat (when implemented):**
- `POST /api/chat` - Interactive AI coaching chat with streaming

## Development Workflow

### Adding New Features
1. Update database models in `app/models/database_models.py`
2. Create/update service in `app/services/`
3. Add API endpoint in `app/routers/`
4. Write tests in `tests/`
5. Update this CLAUDE.md with architecture changes

### Testing Garmin Integration
```bash
# Test authentication
python scripts/sync_data.py --mfa-code 123456

# Force new MFA code to be sent
python scripts/sync_data.py --request-code
```

### Testing AI Analysis
```bash
# Run scheduler job immediately
python scripts/run_scheduler.py --run-now

# Test specific analysis (when implemented)
python -m app.services.ai_analyzer
```

### Debugging
- Logs stored in `logs/` directory
- Use `DEBUG=True` in `.env` for verbose output
- FastAPI auto-reload enabled with `--reload` flag

## Project-Specific Patterns

### Service Initialization
Services use `get_settings()` from `app.config` for dependency injection:
```python
from app.config import get_settings

settings = get_settings()  # Cached singleton
```

### Error Handling in GarminService
- Distinguishes between HTTP errors, MFA failures, and profile fetch issues
- Gracefully falls back when profile API unavailable but OAuth succeeds
- Always call `logout()` in finally block

### AI Prompt Structure
When implementing AIAnalyzer, follow this pattern:
1. Load user profile from config
2. Fetch relevant data (sleep, HRV, activities, training load)
3. Calculate baselines and trends
4. Construct comprehensive prompt with JSON schema
5. Parse and validate Claude response
6. Cache results with hash of input data

### Database Session Management
- Use context managers for session lifecycle
- Commit explicitly after changes
- Roll back on exceptions

## References

- Full specification: `AI_Training_Optimizer_Specification.md`
- **Garmin API Data**: `GARMIN_API_DATA_AVAILABLE.md` - Comprehensive list of all 72 available endpoints
- Detailed schema: See "Database Schema" section in specification
- Workout library: See "Workout Library Integration" in specification
- Training load formulas: See "Training Load Management" in specification

## Available Garmin Data (Quick Reference)

See `GARMIN_API_DATA_AVAILABLE.md` for full details. Key data available:

**For AI Daily Analysis**:
- Sleep: Duration, stages (deep/light/REM), quality score
- HRV: Heart rate variability with baselines
- Resting HR: Daily resting heart rate
- Stress: All-day stress monitoring
- Body Battery: Energy level tracking
- Training Readiness: Garmin's own readiness score

**For Training History**:
- Activities: Full workout history with splits, HR zones, weather
- Training Status: VO2 max, training load balance, status
- Personal Records: PRs across 15+ categories
- Stats: Steps (11,573 today), distance (11.07km), calories (1,806)

**Advanced Metrics**:
- SPO2: Blood oxygen saturation
- Respiration: Breathing rate
- Hydration: Water intake tracking
- Blood Pressure: Manual BP readings
- Weight: Daily weigh-ins

**72 total API methods tested and documented**
