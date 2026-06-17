from core.logging_config import configure_logging
from summary.simple_scheduler import run_daemon


if __name__ == "__main__":
    configure_logging()
    run_daemon()
