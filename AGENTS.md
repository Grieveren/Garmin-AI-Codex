# Repository Guidelines

## Project Structure & Module Organization
- `app/` contains the FastAPI application, organized into `routers/`, `services/`, and `models/` with shared utilities in `config.py` and `database.py`.
- `scripts/` holds operational helpers (`sync_data.py`, `run_scheduler.py`, `initial_setup.py`) used for ingestion, scheduling, and database bootstrapping.
- `tests/` mirrors critical service layers with pytest suites that validate the AI analyzer, Garmin integration, and training planner logic.
- `data/`, `logs/`, and `notebooks/` are reserved for local artifacts, scheduler output, and exploratory analysis; keep sensitive exports out of version control.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` creates the project environment; install dependencies with `pip install -r requirements.txt`.
- `uvicorn app.main:app --reload --port 8002` serves the dashboard and API during development.
- `python scripts/sync_data.py --mfa-code 123456` performs a Garmin sync; omit the MFA flag after the first run.
- `python scripts/run_scheduler.py --run-now` triggers the APScheduler workflow for end-to-end testing.

## Coding Style & Naming Conventions
- Target Python 3.10+ with 4-space indentation, full type hints, and docstrings for public services.
- Run `black .` and `flake8 app tests scripts` before opening a pull request; keep imports sorted and modules snake_case.
- Maintain descriptive PascalCase class names, snake_case functions, and uppercase environment variables defined in `.env`.
- Avoid long controller functions—prefer small service methods under `app/services/` so Garmin and AI logic stays composable.

## Testing Guidelines
- Execute `pytest` from the repository root; use `pytest -k readiness` to scope to new scenarios while iterating.
- Async routes should leverage `pytest-asyncio`; structure tests as `test_<behavior>_...` mirroring the service under test.
- Add fixtures that stub Garmin responses or Anthropic payloads instead of hitting external APIs; store them under `tests/fixtures/` if new files are needed.
- Aim to cover new endpoints and scripts with at least one positive and one failure-path assertion before requesting review.

## Commit & Pull Request Guidelines
- Match the existing log style: start with the feature scope in Title Case, add a colon, then a concise change summary (e.g., `Phase 2 Planner: Add polarized block templates`).
- Keep commits focused; split refactors from feature work so reviewers can trace logic in `app/services/`.
- Pull requests must include a summary of changes, manual test commands, and dashboards screenshots when UI templates under `app/templates/` change.
- Link relevant issues, call out data migrations (`scripts/migrate_phase1_metrics.py`), and note config updates so deployers can refresh `.env`.

## Security & Configuration Tips
- Copy `.env.example` to `.env` and populate `GARMIN_EMAIL`, `GARMIN_PASSWORD`, and `ANTHROPIC_API_KEY`; never commit secrets or raw Garmin exports.
- Rotate cached tokens and delete `logs/` or `data/` artifacts before sharing branches outside the trusted team.
- For local debugging, prefer environment variables over hard-coded credentials and use `filelock` utilities already bundled to avoid race conditions in schedulers.
