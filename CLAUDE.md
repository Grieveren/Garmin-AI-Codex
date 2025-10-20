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

```
User: "Add a new API endpoint for user preferences"
Assistant: [Uses backend-development:backend-architect agent to design and implement]

User: "Why is this query slow?"
Assistant: [Uses database-cloud-optimization:database-optimizer agent to analyze]

User: "Find where authentication is handled"
Assistant: [Uses Explore agent with thoroughness: "medium" to search codebase]

User: "The tests are failing"
Assistant: [Uses debugging-toolkit:debugger agent to diagnose and fix]
```

### Do NOT Use Agents For:
- Simple file reads (use Read tool)
- Basic grep/glob searches (use Grep/Glob tools directly)
- Trivial edits (use Edit tool)
- Health checks and status queries

**Default behavior: When in doubt, use an agent. Prefer specialized agents over doing tasks yourself.**

### Quick Decision Guide

**Need help choosing which agent to use?**

1. **Writing/changing Python code?** → `python-development:python-pro`
2. **Building FastAPI endpoints?** → `python-development:fastapi-pro` or `backend-development:backend-architect`
3. **Finding code/exploring codebase?** → `Explore` agent (specify thoroughness: quick/medium/very thorough)
4. **Tests failing?** → `debugging-toolkit:debugger`
5. **Database query slow?** → `database-cloud-optimization:database-optimizer`
6. **Security concern?** → `comprehensive-review:security-auditor`
7. **Code review before merge?** → `comprehensive-review:code-reviewer`
8. **Not sure?** → `general-purpose` agent

**For code reviews:** Use `comprehensive-review:code-reviewer` for general reviews. Use specialized reviewers (`git-pr-workflows:code-reviewer`, `tdd-workflows:code-reviewer`) only when the context is specific to that workflow.

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

### Review Workflow Benefits:

- Catches issues early before they become problems
- Ensures code quality and architectural integrity
- Provides multiple perspectives on solutions
- Maintains high standards consistently

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

### Root Cause Analysis (2025-10-20):

**Policy Violation**: Implemented 197-line UX/accessibility changes without using frontend agent or mandatory code review.

**Root Causes Identified:**
1. False "simplicity" assessment (CSS feels simple, but 8+ fixes = complex)
2. Misinterpreted "trivial edits" policy (systematic design != trivial)
3. Task momentum bias (kept editing instead of stopping after 3-4 edits)
4. Ignored "automatic and mandatory" language

**Corrective Action Taken:**
- Launched `comprehensive-review:code-reviewer` → found 4 critical WCAG failures
- Launched `accessibility-compliance:ui-visual-validator` → verified compliance
- Fixed all critical issues (contrast, touch targets, focus fallbacks)
- Committed fixes with proper review evidence

**Lessons Learned:**
- Multiple edits = Stop and use agent
- "Mandatory" means no exceptions
- CSS changes can be just as complex as backend code
- Review workflow catches real issues (4 critical failures found)

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

## Complete Agent Reference

### Core Development Agents

**Python Specialists:**
- `python-development:python-pro` - Python 3.12+, async, performance optimization
- `python-development:fastapi-pro` - FastAPI, SQLAlchemy 2.0, Pydantic V2, async APIs
- `python-development:django-pro` - Django 5.x, DRF, Celery, Django Channels

**Backend & API:**
- `backend-development:backend-architect` - API design, microservices, distributed systems
- `backend-development:graphql-architect` - GraphQL federation, performance, security
- `api-scaffolding:backend-architect` - API scaffolding and design
- `api-scaffolding:fastapi-pro` - FastAPI scaffolding
- `api-scaffolding:django-pro` - Django API scaffolding
- `api-scaffolding:graphql-architect` - GraphQL schema design
- `backend-api-security:backend-architect` - Secure API design
- `backend-api-security:backend-security-coder` - Backend security implementation

**Frontend & Mobile:**
- `frontend-mobile-development:frontend-developer` - React 19, Next.js 15
- `frontend-mobile-development:mobile-developer` - React Native, Flutter, native apps
- `multi-platform-apps:frontend-developer` - Multi-platform frontend
- `multi-platform-apps:flutter-expert` - Flutter development
- `multi-platform-apps:ios-developer` - Native iOS with Swift/SwiftUI
- `multi-platform-apps:mobile-developer` - Cross-platform mobile
- `multi-platform-apps:ui-ux-designer` - Design systems, wireframes
- `frontend-mobile-security:frontend-developer` - Frontend security
- `frontend-mobile-security:frontend-security-coder` - XSS prevention, sanitization
- `frontend-mobile-security:mobile-security-coder` - Mobile security patterns

**Other Language Specialists:**
- `javascript-typescript:javascript-pro` - Modern JavaScript ES6+, async
- `javascript-typescript:typescript-pro` - TypeScript, advanced types, generics
- `systems-programming:golang-pro` - Go 1.21+, concurrency, microservices
- `systems-programming:rust-pro` - Rust 1.75+, async, systems programming
- `systems-programming:c-pro` - C, memory management, system calls
- `systems-programming:cpp-pro` - Modern C++, RAII, templates
- `jvm-languages:java-pro` - Java 21+, Spring Boot 3.x, virtual threads
- `jvm-languages:scala-pro` - Scala, functional programming, Spark
- `jvm-languages:csharp-pro` - C#, .NET, async/await
- `web-scripting:php-pro` - Modern PHP, generators, OOP
- `web-scripting:ruby-pro` - Ruby, Rails, metaprogramming
- `functional-programming:elixir-pro` - Elixir, OTP, Phoenix LiveView

### Feature Development & Architecture

**Feature Planning:**
- `feature-dev:code-architect` - Feature architecture design and blueprints
- `feature-dev:code-explorer` - Deep feature analysis and dependency mapping
- `feature-dev:code-reviewer` - Code reviews with confidence-based filtering

**Exploration:**
- `Explore` - Fast codebase exploration (specify thoroughness: quick/medium/very thorough)

**Architecture Review:**
- `code-review-ai:architect-review` - Architecture patterns, clean architecture, DDD
- `comprehensive-review:architect-review` - System design review
- `framework-migration:architect-review` - Migration architecture

### Testing & Quality

**Testing:**
- `unit-testing:test-automator` - AI-powered test automation
- `unit-testing:debugger` - Test failures and debugging
- `full-stack-orchestration:test-automator` - End-to-end test automation
- `performance-testing-review:test-automator` - Performance testing
- `codebase-cleanup:test-automator` - Test coverage improvement
- `backend-development:tdd-orchestrator` - TDD workflow orchestration
- `tdd-workflows:tdd-orchestrator` - TDD best practices enforcement

**Code Review:**
- `comprehensive-review:code-reviewer` - AI-powered code analysis, security, performance
- `code-documentation:code-reviewer` - Code quality for documentation
- `git-pr-workflows:code-reviewer` - PR review workflows
- `tdd-workflows:code-reviewer` - TDD code review
- `code-refactoring:code-reviewer` - Refactoring review
- `codebase-cleanup:code-reviewer` - Code cleanup and quality

**Debugging:**
- `debugging-toolkit:debugger` - Errors, test failures, unexpected behavior
- `error-debugging:debugger` - Error diagnosis and resolution
- `error-diagnostics:debugger` - Error pattern analysis
- `error-debugging:error-detective` - Log analysis, error correlation
- `error-diagnostics:error-detective` - Stack trace analysis

### Database & Data

**Database Design & Optimization:**
- `database-design:database-architect` - Data layer design, schema modeling
- `database-design:sql-pro` - Modern SQL, OLTP/OLAP optimization
- `database-cloud-optimization:database-architect` - Database architecture
- `database-cloud-optimization:database-optimizer` - Query optimization, indexing
- `observability-monitoring:database-optimizer` - Database performance tuning
- `database-migrations:database-admin` - Database administration, migrations
- `database-migrations:database-optimizer` - Migration optimization

**Data Engineering:**
- `data-engineering:backend-architect` - Data backend architecture
- `data-engineering:data-engineer` - Data pipelines, warehouses, streaming
- `machine-learning-ops:data-scientist` - Data analysis, ML modeling, statistics

### AI/ML & LLM Development

**LLM Applications:**
- `llm-application-dev:ai-engineer` - Production LLM apps, RAG systems, agents
- `llm-application-dev:prompt-engineer` - Prompt engineering, optimization

**Machine Learning:**
- `machine-learning-ops:ml-engineer` - ML systems, PyTorch, TensorFlow
- `machine-learning-ops:mlops-engineer` - ML pipelines, MLflow, Kubeflow

### DevOps & Infrastructure

**Cloud Infrastructure:**
- `cloud-infrastructure:cloud-architect` - AWS/Azure/GCP, multi-cloud, IaC
- `cloud-infrastructure:deployment-engineer` - CI/CD, GitOps
- `cloud-infrastructure:hybrid-cloud-architect` - Hybrid/multi-cloud solutions
- `cloud-infrastructure:kubernetes-architect` - K8s, service mesh, GitOps
- `cloud-infrastructure:network-engineer` - Cloud networking, security
- `cloud-infrastructure:terraform-specialist` - Terraform/OpenTofu, IaC
- `deployment-validation:cloud-architect` - Deployment validation

**Deployment & CI/CD:**
- `deployment-strategies:deployment-engineer` - Deployment automation, GitOps
- `deployment-strategies:terraform-specialist` - IaC deployment strategies
- `full-stack-orchestration:deployment-engineer` - Full-stack deployment
- `cicd-automation:deployment-engineer` - CI/CD pipeline design
- `cicd-automation:cloud-architect` - CI/CD cloud architecture
- `cicd-automation:devops-troubleshooter` - CI/CD debugging
- `cicd-automation:kubernetes-architect` - K8s CI/CD
- `cicd-automation:terraform-specialist` - IaC automation

**Kubernetes:**
- `kubernetes-operations:kubernetes-architect` - K8s architecture, service mesh

**Incident Response:**
- `incident-response:devops-troubleshooter` - Incident response, debugging
- `incident-response:incident-responder` - SRE incident management

**Distributed Debugging:**
- `distributed-debugging:devops-troubleshooter` - Distributed system debugging
- `distributed-debugging:error-detective` - Distributed error analysis

### Observability & Performance

**Monitoring & Observability:**
- `observability-monitoring:observability-engineer` - Monitoring, logging, tracing
- `observability-monitoring:performance-engineer` - Performance optimization, OpenTelemetry
- `observability-monitoring:network-engineer` - Network monitoring and optimization
- `application-performance:observability-engineer` - Application observability
- `application-performance:performance-engineer` - App performance optimization
- `application-performance:frontend-developer` - Frontend performance
- `performance-testing-review:performance-engineer` - Performance testing

### Security & Compliance

**Security:**
- `full-stack-orchestration:security-auditor` - DevSecOps, compliance, security automation
- `comprehensive-review:security-auditor` - Security audits and compliance
- `security-scanning:security-auditor` - SAST, vulnerability scanning
- `security-compliance:security-auditor` - Compliance frameworks
- `data-validation-suite:backend-security-coder` - Input validation, security

### Documentation

**Documentation Generation:**
- `documentation-generation:docs-architect` - Technical documentation, architecture guides
- `documentation-generation:api-documenter` - API documentation, OpenAPI
- `documentation-generation:tutorial-engineer` - Step-by-step tutorials
- `documentation-generation:reference-builder` - Technical references
- `documentation-generation:mermaid-expert` - Diagrams (flowcharts, ERDs, architecture)
- `api-testing-observability:api-documenter` - API documentation

### Refactoring & Modernization

**Code Refactoring:**
- `code-refactoring:legacy-modernizer` - Legacy modernization, framework migration
- `dependency-management:legacy-modernizer` - Dependency updates, technical debt
- `framework-migration:legacy-modernizer` - Framework migration strategies

### SEO (Not Applicable to This Project)

This project does not require SEO optimization. SEO-related agents are available but not relevant:
- `seo-content-creation:*` - Content creation and optimization (seo-content-auditor, seo-content-planner, seo-content-writer)
- `seo-technical-optimization:*` - Technical SEO (seo-keyword-strategist, seo-meta-optimizer, seo-snippet-hunter, seo-structure-architect)
- `seo-analysis-monitoring:*` - SEO analytics (seo-authority-builder, seo-cannibalization-detector, seo-content-refresher)

*See Claude Code agent documentation for full details if needed for future projects.*

### Business & Specialized

**Business Functions:**
- `business-analytics:business-analyst` - Business intelligence, KPI frameworks
- `product-manager` - Product strategy, feature prioritization, roadmaps
- `project-manager` - Project planning, coordination, tracking

**Team & Collaboration:**
- `team-collaboration:dx-optimizer` - Developer experience optimization
- `debugging-toolkit:dx-optimizer` - Tooling and workflow improvement

**HR & Legal:**
- `hr-legal-compliance:hr-pro` - HR policies, hiring, compliance
- `hr-legal-compliance:legal-advisor` - Legal documentation, privacy policies

**Marketing & Sales:**
- `customer-sales-automation:customer-support` - Customer support automation
- `customer-sales-automation:sales-automator` - Sales outreach automation
- `content-marketing:content-marketer` - Content marketing strategies
- `content-marketing:search-specialist` - Web research, competitive analysis

### Specialized Domains

**Blockchain:**
- `blockchain-web3:blockchain-developer` - Smart contracts, DeFi, NFTs, DAOs

**Finance:**
- `quantitative-trading:quant-analyst` - Trading strategies, financial models
- `quantitative-trading:risk-manager` - Risk assessment, portfolio management
- `payment-processing:payment-integration` - Stripe, PayPal integration

**Game Development:**
- `game-development:minecraft-bukkit-pro` - Minecraft plugin development
- `game-development:unity-developer` - Unity games, C# scripts

**Accessibility:**
- `accessibility-compliance:ui-visual-validator` - UI testing, visual validation

**Agent SDK:**
- `agent-sdk-dev:agent-sdk-verifier-py` - Python Agent SDK verification
- `agent-sdk-dev:agent-sdk-verifier-ts` - TypeScript Agent SDK verification

**Microcontrollers:**
- `arm-cortex-microcontrollers:arm-cortex-expert` - ARM Cortex development

**Context Management:**
- `agent-orchestration:context-manager` - Multi-agent context orchestration
- `context-management:context-manager` - AI context engineering

### General Purpose

- `general-purpose` - Multi-step tasks, general research
- `statusline-setup` - Status line configuration
- `output-style-setup` - Output style creation

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

## Recommended Agents for This Project

Based on the tech stack (FastAPI, Python, SQLAlchemy, Claude AI, Garmin API), these agents are most relevant:

**Primary Development:**
- `python-development:fastapi-pro` - FastAPI endpoints, routers, async APIs
- `python-development:python-pro` - General Python code, services, utilities
- `llm-application-dev:prompt-engineer` - Claude AI prompt optimization
- `llm-application-dev:ai-engineer` - LLM integration and features

**Database & Performance:**
- `database-cloud-optimization:database-optimizer` - SQLAlchemy query optimization
- `database-cloud-optimization:database-architect` - Schema design, migrations
- `observability-monitoring:performance-engineer` - Performance issues, bottlenecks

**Testing & Quality:**
- `unit-testing:test-automator` - Pytest test creation and automation
- `comprehensive-review:code-reviewer` - Pre-merge code reviews
- `debugging-toolkit:debugger` - Test failures, errors

**Common Task Patterns:**
- **New API endpoint** → `backend-development:backend-architect`
- **Garmin API integration issue** → `error-debugging:debugger` or `error-debugging:error-detective`
- **Database schema change** → `database-cloud-optimization:database-architect`
- **AI analysis improvement** → `llm-application-dev:prompt-engineer`
- **Scheduler/cron job issue** → `cicd-automation:devops-troubleshooter`
- **Query performance** → `database-cloud-optimization:database-optimizer`

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
# Start the FastAPI server (port 8002 to avoid conflicts)
uvicorn app.main:app --reload --port 8002

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

# Migrate database to add Phase 1 enhanced metrics (if upgrading)
python scripts/migrate_phase1_metrics.py
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

**Python 3.14 Compatibility** (`app/compat/pydantic_eval_patch.py`):
- Patches Pydantic's eval_type_backport to handle Python 3.14's updated typing module
- Automatically imported in app/__init__.py to fix compatibility issues
- Prevents "AttributeError: 'str' object has no attribute 'strip'" errors

### Configuration Files (`app/config/prompts.yaml`)

**Centralized Prompt & Threshold Configuration:**
- `prompts.yaml` - Main configuration for AI analysis behavior:
  - Prompt template paths (`readiness_prompt.txt`, `historical_context.txt`)
  - Configurable thresholds (HRV drops, ACWR limits, readiness score ranges)
  - Activity classification rules (training effect thresholds, HR zone thresholds, duration minimums)
  - Multi-language support (default language, translations for EN/DE)

**Prompt Templates** (`app/prompts/`):
- `readiness_prompt.txt` - Main AI readiness analysis prompt with activity type differentiation (~115 lines)
- `historical_context.txt` - Historical training data context template (~44 lines)

**Key Thresholds (Configurable in prompts.yaml):**
```yaml
thresholds:
  readiness:
    critical: 20  # 0-20: Critical - rest day required
    poor: 40      # 21-40: Poor - light activity only
    low: 60       # 41-60: Low - easy workout
    moderate: 75  # 61-75: Moderate - moderate intensity OK
                  # 76-100: High - high intensity OK
  hrv_drop_pct: 10              # HRV drop > 10% signals fatigue
  resting_hr_elevated_bpm: 5    # Resting HR +5bpm signals stress
  sleep_hours_min: 6            # Minimum healthy sleep
  acwr_moderate: 1.3            # ACWR > 1.3 = elevated risk
  acwr_high: 1.5                # ACWR > 1.5 = high injury risk
  no_rest_days: 7               # 7+ consecutive training days = overtraining risk
```

**Activity Classification:**
- High Impact: Training Effect ≥ 3.0, or HR Zones 4-5 > 70% duration, or long duration (>90min)
- Moderate Impact: Training Effect 2.5-3.0, mixed HR zones
- Low Impact: Training Effect < 2.5, yoga, stretching, recovery activities

**Localization:**
- Supports multiple languages (currently EN/DE)
- Configured via `default_language` and `translations` in `prompts.yaml`
- AI responses fully localized including explanations, tips, and recommendations

### Scheduler Design (`scripts/run_scheduler.py`)

- Uses `filelock` to prevent multiple instances
- Runs as standalone process (not embedded in FastAPI)
- Daily job at 8 AM: sync Garmin data → AI analysis → send notification
- `--run-now` flag for immediate execution during development

### Frontend Assets (`app/static/`, `app/templates/`)

**Templates** (`app/templates/`):
- `dashboard.html` - Main dashboard with recommendation-first layout
- Dynamic data rendering with Jinja2 templates
- Responsive design with mobile support

**Static Assets** (`app/static/`):
- `css/dashboard.css` - Custom dashboard styling, recommendation cards, metric displays
- `js/dashboard.js` - Interactive features, data fetching, UI updates
- `images/` - Icons, logos, and UI assets

**Dashboard Architecture**:
- Recommendation-first layout (prioritizes daily AI guidance)
- Real-time data fetching via API endpoints
- Graceful degradation for missing metrics
- Activity type badges (high/moderate/low impact)
- Localized recommendation display (EN/DE)

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

**Phase 2 (AI Engine) - ✅ COMPLETE (Core Features + Enhanced Intelligence):**
- ✅ **Daily readiness analysis (PRODUCTION READY)**
  - Comprehensive AI analysis using Claude Sonnet 4.5
  - Integrates all Phase 1 Enhanced Metrics
  - HRV baseline tracking (7-day, 30-day)
  - ACWR (Acute:Chronic Workload Ratio) calculation
  - Consecutive training day tracking
  - Personalized recommendations: high_intensity/moderate/easy/rest
- ✅ **Activity Type Differentiation (2025-10-19)**
  - Distinguishes between high/moderate/low impact activities
  - Activity classification by training effect, HR zones, duration
  - Nuanced recovery guidance based on activity type
  - 17 comprehensive tests with production-ready error handling
- ✅ **Prompt engineering complete**
  - Detailed Phase 1 metrics usage guidelines
  - Training Status contextualization
  - VO2 Max fitness level interpretation
  - SPO2 and Respiration assessment criteria
  - Activity type interpretation guide with impact levels
- ✅ **Externalized configuration (2025-10-19)**
  - AI prompts in `app/prompts/` (readiness_prompt.txt, historical_context.txt)
  - Configurable thresholds in `app/config/prompts.yaml`
  - Easy tuning without code changes
- ✅ **Multi-language support (2025-10-19)**
  - English and German readiness recommendations
  - Fully localized explanations, tips, and guidance
  - Configurable via `prompts.yaml`
- ⚠️ Training plan generation (backlog)
- ⚠️ Plan adaptation based on recovery metrics (backlog)

**Phase 3 (Web Interface) - 🟡 PARTIAL:**
- ✅ **Dashboard with recommendation-first layout (2025-10-20)**
  - Reorganized to prioritize daily recommendation (user-focused flow)
  - Enhanced visual design with custom CSS (`app/static/css/dashboard.css`)
  - Interactive JavaScript (`app/static/js/dashboard.js`)
  - Displays today's recommendation with full reasoning
- ✅ **Phase 1 Enhanced Recovery Metrics card** (with graceful degradation)
- ✅ **Static assets structure**
  - `app/static/css/` - Custom stylesheets
  - `app/static/js/` - Frontend JavaScript
  - `app/static/images/` - UI assets
- ✅ Manual sync UI with MFA code entry
- ⚠️ Training plan visualization (not started)
- ⚠️ AI chat interface with streaming responses (not started)
- ⚠️ Interactive charts (Plotly/Dash) (not started)

**Phase 4 (Automation) - 🟡 PARTIAL:**
- ✅ Scheduler infrastructure with locking (scripts/run_scheduler.py)
- 🟡 Daily sync job placeholder (logs at 08:00; Garmin sync + AI analysis wiring pending)
- ⚠️ Email/SMS notifications (not implemented)

## Critical Considerations

### Garmin API Reliability ✅ WORKING (Updated 2025-10-18)
The `garminconnect` library reverse-engineers Garmin's web API and is NOT officially supported.

**CURRENT STATUS (2025-10-18)**:
- ✅ **Version**: garminconnect==0.2.30 (currently in requirements.txt)
- ✅ **Authentication**: MFA flow working, tokens cached in `.garmin_tokens/`
- ✅ **Data Retrieval**: ALL critical endpoints working (see GARMIN_API_DATA_AVAILABLE.md)
- ✅ **Python 3.14 Compatibility**: Pydantic eval_type_backport issue resolved via app/compat/pydantic_eval_patch.py
- ✅ **Data Available**: Steps, HR, HRV, sleep, activities, stress, body battery, SPO2, respiration, hydration, training status, and more

**Key Findings**:
- 72 GET methods available in garminconnect
- Most reliable methods: `get_stats()`, `get_heart_rates()`, `get_sleep_data()`, `get_activities()`
- `get_user_summary()` works in 0.2.30 (was broken in 0.2.17)
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

**Training Plans:**
- `GET /api/training/plans/current` - Active training plan (backlog)
- `POST /api/training/plans` - Generate new plan (backlog)
- `PUT /api/training/plans/{id}/workouts/{id}` - Mark workout complete (backlog)

**AI Chat:**
- `POST /api/chat` - Interactive AI coaching chat with streaming (backlog)

## Development Workflow

### Adding New Features
1. Update database models in `app/models/database_models.py`
2. Create/update service in `app/services/`
3. Add API endpoint in `app/routers/`
4. Write tests in `tests/`
5. Update this CLAUDE.md with architecture changes

### Testing Garmin Integration
```bash
# Test authentication (first time or after token expiry)
python scripts/sync_data.py --mfa-code 123456

# Test with existing cached tokens
python scripts/sync_data.py

# Force sync for specific date
python scripts/sync_data.py --date 2025-10-15 --force

# Web UI for MFA (more user-friendly)
# Navigate to http://localhost:8002/manual/mfa
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

### Prompt Externalization Pattern
AI prompts and thresholds are externalized for easy tuning without code changes:

```python
# Load prompt templates
from pathlib import Path
import yaml

# Load config
with open("app/config/prompts.yaml", "r") as f:
    config = yaml.safe_load(f)

# Load prompt template
prompt_path = Path(config["prompt_path"])
with open(prompt_path, "r") as f:
    prompt_template = f.read()

# Access thresholds
hrv_threshold = config["thresholds"]["hrv_drop_pct"]
acwr_high = config["thresholds"]["acwr_high"]

# Use template with formatting
prompt = prompt_template.format(
    user_profile=user_data,
    metrics=current_metrics,
    thresholds=config["thresholds"]
)
```

**Key Files:**
- `app/config/prompts.yaml` - Configuration (thresholds, translations, paths)
- `app/prompts/readiness_prompt.txt` - Main AI prompt template
- `app/prompts/historical_context.txt` - Historical data context

**Benefits:**
- Tune thresholds without code changes
- A/B test different prompt variations
- Easy localization management
- Version control for prompt evolution

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

## Important Notes

### Python 3.14 Compatibility
The codebase includes a compatibility patch for Python 3.14 + Pydantic:
- **Issue**: Pydantic's `eval_type_backport` breaks with Python 3.14's updated `typing` module
- **Fix**: `app/compat/pydantic_eval_patch.py` patches the problematic function
- **Usage**: Automatically imported via `app/__init__.py` - no manual intervention needed
- **When to update**: If Pydantic releases a native fix, remove the patch and update Pydantic version

### Port Configuration
- Default development port: **8002** (to avoid conflicts with other services)
- Configured in .env as `APP_PORT=8002`
- Update uvicorn command: `uvicorn app.main:app --reload --port 8002`

### Database Schema Evolution
- **Phase 1 Enhanced Metrics**: Added via `scripts/migrate_phase1_metrics.py`
- New columns: training_readiness, vo2_max, training_status, spo2, respiration_rate
- Run migration if upgrading from pre-Phase 1 database
