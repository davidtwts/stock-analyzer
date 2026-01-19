# backend/scheduler.py
"""Background scheduler for periodic data updates."""

import logging
from datetime import datetime
from typing import Callable, Optional, TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from backend.config import MARKET_OPEN, MARKET_CLOSE, UPDATE_INTERVAL

if TYPE_CHECKING:
    from backend.data_engine import DataEngine

logger = logging.getLogger(__name__)

# Weekly retry runs every Monday at 10:00 AM Taiwan time (during market hours)
WEEKLY_RETRY_DAY = "mon"
WEEKLY_RETRY_HOUR = 10


class StockScheduler:
    """Manages scheduled stock data updates."""

    def __init__(self, data_engine: Optional["DataEngine"] = None):
        """Initialize the scheduler."""
        self.scheduler = BackgroundScheduler()
        self._update_callback: Optional[Callable] = None
        self._last_update: Optional[datetime] = None
        self._next_update: Optional[datetime] = None
        self._data_engine = data_engine

    def is_market_open(self) -> bool:
        """Check if Taiwan market is currently open."""
        now = datetime.now().time()
        weekday = datetime.now().weekday()

        # Closed on weekends
        if weekday >= 5:
            return False

        return MARKET_OPEN <= now <= MARKET_CLOSE

    def set_update_callback(self, callback: Callable):
        """Set the callback function for updates."""
        self._update_callback = callback

    def _run_update(self):
        """Execute the update callback."""
        if self._update_callback:
            logger.info("Running scheduled update...")
            self._last_update = datetime.now()
            try:
                self._update_callback()
                logger.info("Update completed successfully")
            except Exception as e:
                logger.error(f"Update failed: {e}")

    def _run_weekly_retry(self):
        """Retry quarantined tickers during market hours."""
        if not self._data_engine:
            logger.warning("Weekly retry skipped: no data engine configured")
            return

        if not self.is_market_open():
            logger.debug("Weekly retry skipped: market closed")
            return

        candidates = self._data_engine._health.get_retry_candidates()
        if not candidates:
            logger.info("Weekly retry: no candidates to retry")
            return

        logger.info(f"Weekly retry: attempting {len(candidates)} quarantined symbols")
        for symbol in candidates:
            result = self._data_engine.fetch_and_process(symbol)
            if result is None:
                # Fetch failed, update retry schedule for next week
                self._data_engine._health.update_retry_schedule(symbol)

    def start(self):
        """Start the scheduler."""
        # Regular update job (every UPDATE_INTERVAL seconds)
        self.scheduler.add_job(
            self._run_update,
            trigger=IntervalTrigger(seconds=UPDATE_INTERVAL),
            id="stock_update",
            replace_existing=True,
        )

        # Weekly retry job (every Monday at 10:00 AM during market hours)
        if self._data_engine:
            self.scheduler.add_job(
                self._run_weekly_retry,
                trigger=CronTrigger(day_of_week=WEEKLY_RETRY_DAY, hour=WEEKLY_RETRY_HOUR),
                id="weekly_retry",
                replace_existing=True,
            )
            logger.info(f"Weekly retry job scheduled ({WEEKLY_RETRY_DAY} at {WEEKLY_RETRY_HOUR}:00)")

        self.scheduler.start()
        logger.info(f"Scheduler started (interval: {UPDATE_INTERVAL}s)")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    @property
    def last_update(self) -> Optional[datetime]:
        """Get last update time."""
        return self._last_update

    @property
    def next_update(self) -> Optional[datetime]:
        """Get next scheduled update time."""
        job = self.scheduler.get_job("stock_update")
        if job:
            return job.next_run_time
        return None
