# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent Usage Policy

**CRITICAL: Use specialized agents proactively for all non-trivial tasks.** Do not attempt complex tasks yourself when agents are available.

### When to Use Agents (ALWAYS):

**Code Implementation & Architecture:**
- Use `python-development:python-pro` for Python code changes, refactoring, or new features
- Use `feature-dev:code-architect` for feature planning and architecture design
- Use `backend-development:backend-architect` for API design and backend architecture
- Use `comprehensive-review:code-reviewer` after implementing features

**Code Analysis & Exploration:**
- Use `Explore` agent (with thoroughness level) for codebase exploration and understanding
- Use `feature-dev:code-explorer` for deep feature analysis and dependency mapping
- Use `error-debugging:debugger` for debugging errors and failures

**Testing & Quality:**
- Use `unit-testing:test-automator` for test creation and test coverage
- Use `debugging-toolkit:debugger` for test failures and unexpected behavior

**Database & Performance:**
- Use `database-cloud-optimization:database-optimizer` for query optimization
- Use `observability-monitoring:performance-engineer` for performance issues

**Security & Review:**
- Use `comprehensive-review:security-auditor` for security audits
- Use `comprehensive-review:architect-review` for architectural review

### Agent Usage Examples:
- New API endpoint → `backend-development:backend-architect`
- Slow query → `database-cloud-optimization:database-optimizer`
- Codebase search → `Explore` agent (thoroughness: quick/medium/very thorough)
- Test failures → `debugging-toolkit:debugger`

### Do NOT Use Agents For:
- Simple file reads (use Read tool)
- Basic grep/glob searches (use Grep/Glob tools directly)
- Trivial edits (use Edit tool)
- Health checks and status queries

**Default behavior: When in doubt, use an agent. Prefer specialized agents over doing tasks yourself.**

### Project-Specific Agent Patterns

Common task-to-agent mappings for this codebase:

- **New API endpoint** → `backend-development:backend-architect`
- **Garmin API integration issue** → `error-debugging:debugger` or `error-debugging:error-detective`
- **Database schema change** → `database-cloud-optimization:database-architect`
- **AI analysis improvement** → `llm-application-dev:prompt-engineer`
- **Scheduler/cron job issue** → `cicd-automation:devops-troubleshooter`
- **Query performance** → `database-cloud-optimization:database-optimizer`

---

## Review Workflow Policy

**CRITICAL: Always initiate reviews after completing work or when agents finish tasks.**

### After I Complete Work:

- **Code changes/implementations** → Launch `comprehensive-review:code-reviewer`
- **Architecture decisions** → Launch `code-review-ai:architect-review`
- **Security-sensitive changes** → Launch `comprehensive-review:security-auditor`
- **Feature implementations** → Launch `feature-dev:code-reviewer`
- **Database schema changes** → Launch `database-cloud-optimization:database-architect`
- **Prompt/AI changes** → Launch `llm-application-dev:prompt-engineer`

### After an Agent Completes Work:

- Review agent output for completeness and correctness
- Verify work addresses original requirements
- Check for issues or gaps needing follow-up
- If needed, launch complementary review agent (e.g., security review after code review)

**This workflow is automatic and mandatory - apply it proactively without user prompting.**

### Workflow Enforcement Checkpoints:

**STOP and use an agent when:**
1. Task requires 5+ Edit tool calls
2. Implementing design systems or UI patterns
3. Making accessibility-sensitive changes
4. Working on security-critical code
5. Unsure if task is "trivial" - default to using agent

**STOP and launch review when:**
1. About to commit code changes
2. Completed any non-trivial implementation
3. Agent finishes work
4. Making changes to user-facing interfaces
5. Modifying security or accessibility features

**"Trivial" means:**
- Single typo fix
- One-line comment addition
- Variable rename (1-2 occurrences)
- NOT: Multiple edits, system changes, UI work

---

## Response Style

**CRITICAL: Keep responses concise and actionable.**

- Maximum 3-5 sentences for confirmations and status updates
- Use bullet points instead of paragraphs when listing items
- Avoid tables unless explicitly requested
- Skip emojis and decorative formatting
- Only provide summaries when asked
- For tool results: state outcome in 1-2 sentences, don't repeat details

**CRITICAL: Always think deeply before responding.**

- Use extended thinking for problem-solving, analysis, and decision-making
- Think through implications, edge cases, and alternatives
- Reason about trade-offs before recommending solutions
- Consider context from CLAUDE.md, codebase patterns, and user goals
- Don't rush to answers - thorough thinking leads to better outcomes

---

## Git Workflow Policy

**CRITICAL: Always use feature branches. NEVER commit directly to main.**

### Branch Naming Convention:
- **Features:** `feature/description` (e.g., `feature/hr-zone-calculation`)
- **Fixes:** `fix/description` (e.g., `fix/garmin-api-endpoint`)
- **Experiments:** `experiment/description` (e.g., `experiment/alternative-ai-prompt`)
- **Refactoring:** `refactor/description` (e.g., `refactor/data-processor`)

### Workflow (Solo Developer + AI Agent):

**Tier 1: Most Changes (90% of work)**
```bash
# 1. Create branch (prevents accidental main commits)
git checkout -b fix/your-feature

# 2. Make changes, commit with descriptive message
git add .
git commit -m "Descriptive commit message"

# 3. Merge directly to main (no PR needed)
git checkout main
git merge fix/your-feature --ff-only  # Fast-forward merge
# OR: git merge fix/your-feature --squash  # Single clean commit

# 4. Push to remote
git push

# 5. Delete feature branch
git branch -d fix/your-feature
```

**Tier 2: Major Features (10% of work - Optional PR)**
Use full PR workflow when:
- Making architectural changes you want documented in PR history
- Running CI/CD validation before merging
- Changes you might want to revert easily
- Features you want to share/discuss with others

```bash
git checkout -b feature/major-change
# ... make changes, commit ...
git push -u origin feature/major-change
# Create PR on GitHub → Review → Merge via web interface
```

### Enforcement:
- Pre-commit hook **blocks** direct commits to `main` branch
- Forces branch creation (prevents accidents)
- Bypass only with `--no-verify` (emergency use only)

### Exception Policy:
**Direct commits to main are ONLY allowed for:**
- Critical production hotfixes (with explicit user approval)
- Should be extremely rare (< 1% of commits)

**Rationale:**
- **Prevents accidents** - Can't accidentally commit incomplete work to main
- **Clean history** - `--squash` option creates single commit per feature
- **Easy rollback** - Can revert entire feature with one command
- **Flexible** - No mandatory PR overhead for small changes
- **Real-time review** - Code review happens during AI conversation, not after

---

## Project Overview

AI-Powered Training Optimization System that fetches Garmin fitness data, analyzes it using Claude AI, and generates adaptive daily workout recommendations. The system prevents overtraining through intelligent load management and provides personalized coaching based on recovery metrics (HRV, sleep, resting HR).

## Tech Stack

- **Python 3.10+** with FastAPI
- **garminconnect** - Unofficial Garmin API client (may break if Garmin updates)
- **Anthropic Claude API** (claude-sonnet-4-5-20250929) for AI analysis with multi-language support
- **SQLAlchemy** with SQLite (upgradeable to PostgreSQL)
- **APScheduler** for automated daily syncing
- **Pydantic Settings** for configuration management
- **YAML-based configuration** for prompts, thresholds, and localization (EN/DE)

## Common Development Commands

### Setup & Running
```bash
# Environment setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env

# Start FastAPI server (port 8002)
uvicorn app.main:app --reload --port 8002

# Run scheduler (separate terminal)
python scripts/run_scheduler.py --run-now

# Manual Garmin sync with MFA
python scripts/sync_data.py --mfa-code 123456
```

### Docker & Testing
```bash
# Docker deployment
docker-compose up -d && docker-compose logs -f

# Run tests
pytest -v tests/test_garmin_service.py
```

### Database Operations
```bash
python scripts/initial_setup.py              # Initialize schema
python scripts/backfill_data.py --days 90   # Backfill historical data
python scripts/migrate_phase1_metrics.py     # Phase 1 migration
python scripts/migrate_recovery_time.py      # Add recovery time tracking
```

---

## Architecture

### Core Service Layer (`app/services/`)

**GarminService** - Handles all Garmin Connect API interactions with MFA token caching:
- Token-based authentication with persistent storage (`.garmin_tokens`)
- Handles MFA authentication flow (user provides 6-digit code)
- Gracefully degrades when profile API calls fail but OAuth succeeds
- **Detailed activity data**: Fetches splits, HR zones, weather via `get_detailed_activity_analysis(activity_id)`
- Critical: `garminconnect` library is unofficial and may break with Garmin API changes

**AIAnalyzer** - Claude AI integration for workout analysis:
- Daily readiness analysis based on sleep, HRV, resting HR, training load
- **Activity type differentiation**: Distinguishes between high/moderate/low impact activities (yoga vs running vs cycling)
- **Nuanced recovery recommendations**: Accounts for activity type in recovery guidance (e.g., yoga after hard run vs another hard run)
- Workout recommendations (high_intensity, moderate, easy, rest)
- Training plan adaptation based on recovery metrics
- Uses comprehensive prompt engineering with user profile, physiological data, and training history
- **Multi-language support**: Responses in English or German (configurable)
- **Externalized prompts**: Templates in `app/prompts/`, thresholds in `app/config/prompts.yaml` for easy tuning

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

**ActivityDetailService** - Fetches and caches detailed activity data:
- Combines GarminService API calls with database caching
- Fetches splits (lap-by-lap pace/HR), HR zone distribution, weather conditions
- Calculates derived metrics: pace consistency score, HR drift percentage
- Smart caching: 24-hour cache for complete data, 1-hour retry for incomplete
- Bulk fetch with rate limiting for recent activities

**ActivityDetailHelper** - Helper for activity detail storage and calculations:
- Pace consistency scoring (0-100 based on coefficient of variation)
- HR drift calculation (percentage increase/decrease from start to finish)
- Cache validation and refetch logic

**AlertDetector** - Detects training alerts based on physiological metrics:
- **Alert Types**: Overtraining, illness risk, injury risk
- **Overtraining Detection**: HRV drops, consecutive hard training days, sleep debt
- **Illness Detection**: Combined HRV drop + elevated resting HR patterns
- **Injury Detection**: ACWR thresholds, weekly load increases
- Scientifically-backed thresholds from `app/config/prompts.yaml`
- Stores alerts in `training_alerts` table with severity levels (warning/critical)
- Alert deduplication with optimistic locking pattern
- Integrated with AIAnalyzer for automatic daily detection

### Database Models (`app/models/database_models.py`)

Key tables (refer to AI_Training_Optimizer_Specification.md for full schema):
- `daily_metrics` - Steps, HR, HRV, sleep, body battery, recovery time (hours until ready for next quality workout)
- `sleep_sessions` - Detailed sleep stage data
- `activities` - Garmin workouts with training effect/load
- **`activity_details`** - Detailed activity data (splits, HR zones, weather) with derived metrics
- **`training_alerts`** - Training alerts (overtraining, illness, injury) with severity, triggers, and lifecycle tracking
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

**Python 3.14 Compatibility** (`app/compat/pydantic_eval_patch.py`):
- Patches Pydantic's eval_type_backport to handle Python 3.14's updated typing module
- Automatically imported in app/__init__.py to fix compatibility issues
- Prevents "AttributeError: 'str' object has no attribute 'strip'" errors

### Configuration Files (`app/config/prompts.yaml`)

**Centralized Prompt & Threshold Configuration:**
- Prompt templates: `app/prompts/readiness_prompt.txt`, `historical_context.txt`
- Configurable thresholds: HRV drops, ACWR limits, readiness score ranges
- Activity classification: Training effect, HR zones, duration rules
- Multi-language support: EN/DE translations

### Scheduler Design (`scripts/run_scheduler.py`)

- Uses `filelock` to prevent multiple instances
- Runs as standalone process (not embedded in FastAPI)
- Daily job at 8 AM: sync Garmin data → AI analysis → send notification
- `--run-now` flag for immediate execution during development

### Frontend (`app/static/`, `app/templates/`)
- `dashboard.html` - Recommendation-first layout, Jinja2 templates, responsive design
- `css/dashboard.css` - Custom styling, recommendation cards, metric displays
- `js/dashboard.js` - Interactive features, data fetching, UI updates
- Features: Real-time API fetching, graceful degradation, activity badges, localized display (EN/DE)

---

## Implementation Status

**Current:** MVP ~90% Complete (Core features done, automation in progress)

For detailed roadmap, see **[ROADMAP.md](./ROADMAP.md)**

**Phase 1 (Foundation) - ✅ COMPLETE (100%):**
- Garmin API integration with MFA token caching
- SQLAlchemy database with enhanced metrics (Training Readiness, VO2 Max, Training Status, SPO2, Respiration)
- 90 days historical data backfill capability
- Dashboard with Phase 1 metrics and graceful degradation

**Phase 2 (AI Engine) - ✅ COMPLETE (100%):**
- Daily readiness analysis using Claude Sonnet 4.5
- Activity type differentiation (high/moderate/low impact)
- HRV baseline tracking, ACWR calculation, personalized recommendations
- Externalized prompts (`app/prompts/`) and thresholds (`app/config/prompts.yaml`)
- Multi-language support (EN/DE)
- 17 comprehensive tests with production-ready error handling

**Phase 3 (Web Interface) - ✅ COMPLETE (95%):**
- ✅ Dashboard with recommendation-first layout
- ✅ Manual sync UI with MFA entry
- ✅ Responsive design with custom CSS/JS
- ⚠️ Training plan visualization, AI chat, interactive charts (backlog)

**Phase 4 (Automation) - 🟡 IN PROGRESS (70%):**
- ✅ Scheduler infrastructure with file locking and daily sync
- ✅ AI analysis automation integrated
- ⚠️ Alert detection system (overtraining, illness, injury risk - needs implementation)
- ⚠️ Plan adaptation logic (automatic workout rescheduling - needs integration)
- Note: Email/SMS notifications deferred to Phase 5 (mobile app with push notifications)

**Immediate Priorities (Email/SMS notifications deferred to mobile app):**
1. Implement alert detection system (overtraining, illness, injury risk)
2. Build plan adaptation logic (automatic workout rescheduling)
3. Production hardening (logging, monitoring, security, backups)
4. Testing and documentation

---

## Critical Considerations

### Garmin API (garminconnect==0.2.30) ✅ WORKING
**Unofficial library - may break with Garmin updates.**
- ✅ MFA flow working, tokens cached in `.garmin_tokens/`
- ✅ 72 GET methods available (see GARMIN_API_DATA_AVAILABLE.md)
- ✅ Python 3.14 compatible via `app/compat/pydantic_eval_patch.py`

**If API breaks:** Check github.com/cyberjunky/python-garminconnect issues, test with `python3 -m scripts.sync_data --mfa-code CODE`

### MFA Authentication
First login requires 6-digit code. Tokens cached for subsequent logins. Delete `.garmin_tokens` to re-authenticate.

### AI Analysis Costs
~$0.10-0.20/day ($5-15/month). Uses prompt caching and 24hr response cache (`ai_analysis_cache` table).

### Training Load Formulas
- **ACWR**: 0.8-1.3 optimal, >1.5 high injury risk
- **Fitness/Fatigue/Form**: 42-day/7-day EWMA, Form = Fitness - Fatigue

### Scheduler
ONE instance only (enforced via filelock). Run as systemd/Docker/cloud scheduler, separate from web app.

---

## API Endpoints

**System:**
- `GET /health` - Health check
- `GET /` - Dashboard home (redirects to /dashboard)
- `GET /dashboard` - Main dashboard with today's recommendation

**Data Sync:**
- `POST /api/sync/manual` - Trigger manual Garmin sync (JSON endpoint)
- `GET /manual/sync/now` - Manual sync UI
- `GET /manual/mfa` - MFA code entry form
- `POST /manual/mfa` - Submit MFA code
- `POST /manual/mfa/request` - Request new MFA code

**Recommendations:**
- `GET /api/recommendations/today` - Today's AI-generated workout (✅ IMPLEMENTED)
- `POST /api/recommendations/adapt-plan` - Modify plan based on readiness (backlog)

**Alerts:**
- `GET /api/alerts/active?days=7` - Get active training alerts from last N days (✅ IMPLEMENTED)
- `POST /api/alerts/{alert_id}/acknowledge` - Mark alert as acknowledged (✅ IMPLEMENTED)

**Training Plans:**
- `GET /api/training/plans/current` - Active training plan (backlog)
- `POST /api/training/plans` - Generate new plan (backlog)
- `PUT /api/training/plans/{id}/workouts/{id}` - Mark workout complete (backlog)

**AI Chat:**
- `POST /api/chat` - Interactive AI coaching chat with streaming (backlog)

---

## Development Workflow

### Adding Features
1. Update `app/models/database_models.py`
2. Create/update service in `app/services/`
3. Add API endpoint in `app/routers/`
4. Write tests in `tests/`
5. Update CLAUDE.md with architecture changes

### Testing & Debugging
- **Garmin Integration:** `python scripts/sync_data.py --mfa-code 123456` or web UI at `/manual/mfa`
- **Activity Details:** `python scripts/fetch_activity_details.py --activity-id 12345678` or `--recent-days 30`
- **AI Analysis:** `python scripts/run_scheduler.py --run-now`
- **Debugging:** Logs in `logs/`, use `DEBUG=True` in `.env`

---

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

### Prompt Externalization Pattern
AI prompts in `app/prompts/`, thresholds in `app/config/prompts.yaml` for runtime tuning.

**Key Files:**
- `app/config/prompts.yaml` - Thresholds, translations, template paths
- `app/prompts/readiness_prompt.txt` - Main AI prompt template
- `app/prompts/historical_context.txt` - Historical data context

**Benefits:** Tune thresholds without code changes, A/B test prompts, easy localization, version-controlled prompt evolution

### Database Session Management
- Use context managers for session lifecycle
- Commit explicitly after changes
- Roll back on exceptions

---

## References

- **Project Roadmap**: `ROADMAP.md` - Detailed implementation timeline, status, and priorities
- Full specification: `AI_Training_Optimizer_Specification.md`
- **Garmin API Data**: `GARMIN_API_DATA_AVAILABLE.md` - Comprehensive list of all 72 available endpoints
- Detailed schema: See "Database Schema" section in specification
- Workout library: See "Workout Library Integration" in specification
- Training load formulas: See "Training Load Management" in specification

## Important Notes

**Python 3.14:** Compatibility patch in `app/compat/pydantic_eval_patch.py` (auto-imported). Remove when Pydantic fixes upstream.

**Port:** Default 8002 (avoid conflicts). Set `APP_PORT=8002` in `.env`.

**Migrations:** Use `scripts/migrate_phase1_metrics.py` when upgrading to Phase 1 Enhanced Metrics.
