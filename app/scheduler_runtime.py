import logging
import threading

from app.config import ENABLE_SUMMARY_SCHEDULER


logger = logging.getLogger(__name__)
_summary_thread: threading.Thread | None = None
_summary_stop_event: threading.Event | None = None


def start_summary_scheduler() -> None:
    global _summary_thread, _summary_stop_event

    if not ENABLE_SUMMARY_SCHEDULER:
        logger.info("Summary scheduler is disabled. Set ENABLE_SUMMARY_SCHEDULER=true to enable it.")
        return

    if _summary_thread and _summary_thread.is_alive():
        logger.info("Summary scheduler is already running.")
        return

    from summary.scheduler import run_daemon

    _summary_stop_event = threading.Event()
    _summary_thread = threading.Thread(
        target=run_daemon,
        kwargs={"stop_event": _summary_stop_event},
        name="carenote-summary-scheduler",
        daemon=True,
    )
    _summary_thread.start()
    logger.info("Summary scheduler started.")


def stop_summary_scheduler(timeout: float = 5.0) -> None:
    global _summary_thread, _summary_stop_event

    if not _summary_thread:
        return

    if _summary_stop_event:
        _summary_stop_event.set()

    _summary_thread.join(timeout=timeout)
    if _summary_thread.is_alive():
        logger.warning("Summary scheduler did not stop within %.1f seconds.", timeout)
    else:
        logger.info("Summary scheduler stopped.")

    _summary_thread = None
    _summary_stop_event = None
