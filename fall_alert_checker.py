from core.logging_config import configure_logging
from detection.pipeline import main, process_text_content, process_text_file


__all__ = ["process_text_content", "process_text_file"]


if __name__ == "__main__":
    configure_logging()
    raise SystemExit(main())
