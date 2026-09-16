import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.jobs.reminders import generate_daily_reminders

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(daemon=True)


def scheduled_daily_reminders():
    db = SessionLocal()
    try:
        created = generate_daily_reminders(db)
        if created:
            logger.info(f"Generated {len(created)} new reminders.")
    except Exception as e:
        logger.error(f"Error generating daily reminders: {e}")
    finally:
        db.close()


def start_scheduler():
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if not scheduler.running:
        scheduler.add_job(
            scheduled_daily_reminders,
            "cron",
            hour=8,
            minute=0,
            id="daily_reminders",
            replace_existing=True
        )
        scheduler.start()
        # Trigger an initial run in background
        scheduler.add_job(scheduled_daily_reminders, id="initial_reminders")
        logger.info("APScheduler started successfully.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
