"""Standalone scheduler process for the training optimizer."""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from filelock import FileLock

from app.config import Settings, get_settings
from app.logging_config import configure_logging
from app.database import SessionLocal, run_migrations
from app.services.ai_analyzer import AIAnalyzer
from app.services.garmin_service import GarminService
from scripts.sync_data import (
    fetch_and_save_activities,
    fetch_daily_metrics,
    save_daily_metric,
)


logger = logging.getLogger("scheduler")


def acquire_lock(lock_path: Path) -> FileLock:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(lock_path))
    lock.acquire(timeout=0)
    return lock


def perform_daily_sync() -> Dict[str, Dict[str, Any]]:
    """
    Run Garmin sync for yesterday and today, returning a summary per date.

    Returns:
        dict: mapping ISO date -> summary payload with metrics/activities status
    """
    garmin = GarminService()
    db = SessionLocal()
    summary: Dict[str, Dict[str, Any]] = {}
    target_dates = [date.today() - timedelta(days=1), date.today()]

    try:
        try:
            garmin.login()
        except Exception:
            logger.exception("Garmin login failed")
            raise
        logger.info("Logged into Garmin successfully")

        for target_date in target_dates:
            date_key = target_date.isoformat()
            date_summary: Dict[str, Any] = {
                "metrics": "not-fetched",
                "activities_saved": 0,
                "activities_skipped": 0,
            }

            metrics = fetch_daily_metrics(garmin, target_date, verbose=False)
            if metrics:
                saved = save_daily_metric(db, metrics, force=False, verbose=False)
                date_summary["metrics"] = "saved" if saved else "skipped"
            else:
                date_summary["metrics"] = "missing"
                logger.warning("No daily metrics returned for %s", date_key)

            saved_count, skipped_count = fetch_and_save_activities(
                garmin, target_date, db, force=False, verbose=False
            )
            date_summary["activities_saved"] = saved_count
            date_summary["activities_skipped"] = skipped_count

            summary[date_key] = date_summary
            logger.info(
                "Sync summary for %s | metrics=%s | activities_saved=%d | activities_skipped=%d",
                date_key,
                date_summary["metrics"],
                saved_count,
                skipped_count,
            )

        return summary
    except Exception:
        db.rollback()
        logger.exception("Unhandled error during Garmin sync loop")
        raise
    finally:
        db.close()
        try:
            garmin.logout()
        except Exception:
            logger.debug("Garmin logout raised but was ignored", exc_info=True)


async def run_daily_job() -> None:
    start = datetime.now(timezone.utc)
    logger.info("Daily scheduler job started")

    try:
        sync_summary = await asyncio.to_thread(perform_daily_sync)
    except Exception:
        logger.exception("Daily sync failed")
        return

    try:
        analyzer = AIAnalyzer()
        readiness = await analyzer.analyze_daily_readiness(date.today())
    except Exception:
        logger.exception("AI readiness analysis failed")
    else:
        logger.info(
            "AI readiness | score=%s | recommendation=%s | confidence=%s",
            readiness.get("readiness_score"),
            readiness.get("recommendation"),
            readiness.get("confidence"),
        )

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("Daily scheduler job finished in %.2fs", elapsed)
    for iso_date, details in sync_summary.items():
        logger.debug("Detail %s -> %s", iso_date, details)


async def run_once() -> None:
    await run_daily_job()


async def main(run_now: bool) -> None:
    configure_logging()
    settings = get_settings()
    run_migrations()

    scheduler_log = settings.log_dir / "scheduler.log"
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(scheduler_log) for h in logger.handlers):
        handler = logging.FileHandler(scheduler_log, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        logger.addHandler(handler)

    lock_path = settings.scheduler_lock_file
    lock = acquire_lock(lock_path)
    logger.info("Acquired scheduler lock at %s", lock_path)
    try:
        if run_now:
            await run_once()
            return

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            run_daily_job,
            "cron",
            hour=settings.scheduler_hour,
            minute=settings.scheduler_minute,
        )
        scheduler.start()

        logger.info(
            "Scheduler running (cron %02d:%02d). Press Ctrl+C to exit.",
            settings.scheduler_hour,
            settings.scheduler_minute,
        )
        await asyncio.Event().wait()
    finally:
        lock.release()
        logger.info("Released scheduler lock at %s", lock_path)
        if lock_path.exists():
            lock_path.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run scheduler process")
    parser.add_argument("--run-now", action="store_true", help="Execute job immediately and exit")
    args = parser.parse_args()

    try:
        asyncio.run(main(run_now=args.run_now))
    except TimeoutError:
        logger.warning("Scheduler already running; exiting.")
