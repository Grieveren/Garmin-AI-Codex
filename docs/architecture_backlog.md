# Architecture Backlog

_Last updated: 2025-10-18_

This living document captures post-MVP architecture and reliability work. Use it to create focused branches/issues and to track progress as items move from planning to done.

## Phase 1.5 Priorities

Each item is scoped to be tackled in its own branch/PR for ease of review.

1. **Scheduler Integration** _(✅ completed)_ — wire `scripts/run_scheduler.py` to execute the Garmin sync + AI readiness analysis outside the web process.
   - Replace the placeholder job with calls into the existing sync/analysis services.
   - Ensure the locking strategy prevents concurrent runs across environments.
   - Add logging around job start/end and failure scenarios.

2. **Configuration & Secrets Hardening** _(✅ completed)_ — enforce environment-based settings across the stack.
   - Require critical keys (Garmin, Anthropic, secret key) at startup via Pydantic validation.
   - Document environment overrides and default ports/hosts.
   - Remove hard-coded fallbacks that mask missing configuration.

3. **Logging & Observability** _(✅ completed)_ — centralize structured logs for Garmin and AI calls.
   - Introduce a shared logger (JSON-friendly) and consistent log levels.
   - Capture request/response summaries (without secrets) for sync jobs and API calls.
   - Define an error-handling pattern so failures surface in one place.

4. **Testing Expansion** _(✅ completed)_ — improve automated coverage beyond unit tests.
   - Add end-to-end tests that stub Garmin responses and assert the readiness JSON payload.
   - Provide fixtures for scheduler jobs so they can be invoked inside pytest.
   - Guard against regressions when AI prompt/config changes.

5. **AI Prompt & Config Refactor** — externalize prompt templates and thresholds.
   - Store Claude prompts and recommendation thresholds as versioned files/config entries.
   - Load them through a dedicated settings object for easier experimentation.
   - Document the process for updating prompts/models safely.

6. **Persistence & Frontend Follow-up (Optional)** — tackle once the above are stable.
   - Prepare for PostgreSQL by ensuring migrations cover new fields and transactions are scoped properly.
   - Consider extracting the dashboard assets (CSS/JS) into a separate static bundle for richer charting/chat work.

## How to Use This Backlog

- Create a branch per bullet (e.g., `architecture/scheduler-integration`) and reference this doc in the PR description.
- Update the relevant bullet with status notes (`✅`, `🛠️ in progress`, or links to tickets) as work lands.
- Feel free to append new architecture items here rather than burying them in the specification.
