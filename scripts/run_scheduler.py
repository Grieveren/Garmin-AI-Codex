"""Standalone scheduler process for the training optimizer."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from filelock import FileLock


LOCK_PATH = Path(".scheduler.lock")


def acquire_lock() -> FileLock:
    lock = FileLock(str(LOCK_PATH))
    lock.acquire(timeout=0)
    return lock


async def run_daily_job() -> None:
    now = datetime.now().isoformat()
    print(f"[{now}] Daily job placeholder: sync + analysis not yet implemented")


async def run_once() -> None:
    await run_daily_job()


async def main(run_now: bool) -> None:
    lock = acquire_lock()
    try:
        if run_now:
            await run_once()
            return

        scheduler = AsyncIOScheduler()
        scheduler.add_job(run_daily_job, "cron", hour=8, minute=0)
        scheduler.start()

        print("Scheduler running. Press Ctrl+C to exit.")
        await asyncio.Event().wait()
    finally:
        lock.release()
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run scheduler process")
    parser.add_argument("--run-now", action="store_true", help="Execute job immediately and exit")
    args = parser.parse_args()

    try:
        asyncio.run(main(run_now=args.run_now))
    except TimeoutError:
        print("Scheduler already running; exiting.")
