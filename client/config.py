import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BASE_URL = os.getenv(
    "CARENOTE_SERVER_URL",
    "http://127.0.0.1:9000",
).rstrip("/")

ANALYZE_URL = f"{BASE_URL}/analyze-video/"
HEALTH_URL = f"{BASE_URL}/health"

LOG_FILE = os.getenv(
    "CARENOTE_CLIENT_LOG_FILE",
    str(PROJECT_ROOT / "logs" / "send_video.log"),
)

REQUEST_TIMEOUT = (10, 1800)
DELETE_LOCAL_VIDEO_AFTER_SEND = os.getenv("DELETE_LOCAL_VIDEO_AFTER_SEND", "true").lower() == "true"

FILE_STABLE_CHECKS = 3
FILE_STABLE_INTERVAL_SEC = 1
