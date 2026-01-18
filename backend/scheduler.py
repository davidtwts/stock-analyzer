# backend/scheduler.py
"""Background scheduler for periodic data updates."""

import logging
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import MARKET_OPEN, MARKET_CLOSE, UPDATE_INTERVAL

logger = logging.getLogger(__name__)


class StockScheduler:
    """Manages scheduled stock data updates."""

    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler = BackgroundScheduler()
        self._update_callback: Optional[Callable] = None
        self._last_update: Optional[datetime] = None
        self._next_update: Optional[datetime] = None

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

    def start(self):
        """Start the scheduler."""
        self.scheduler.add_job(
            self._run_update,
            trigger=IntervalTrigger(seconds=UPDATE_INTERVAL),
            id="stock_update",
            replace_existing=True,
        )
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
