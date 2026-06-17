import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHECKPOINT_PATH = os.getenv("CHECKPOINT_PATH", "/workspace/models/qwen3-vl-8b-instruct-fp8")
BASE_RESULT_DIR = os.getenv("BASE_RESULT_DIR", "/workspace/development/generated_data")
SUMMARY_DIR = os.getenv("SUMMARY_DIR", os.path.join(BASE_RESULT_DIR, "summaries"))

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(1024 * 1024 * 1024)))
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
EMAIL_ALERT_ENABLED = os.getenv("EMAIL_ALERT_ENABLED", "true").lower() == "true"
MODEL_TIMEOUT_SEC = float(os.getenv("MODEL_TIMEOUT_SEC", "60"))
ENABLE_SUMMARY_SCHEDULER = os.getenv("ENABLE_SUMMARY_SCHEDULER", "true").lower() == "true"

AGENT_DVR_BASE_URL = os.getenv("AGENT_DVR_BASE_URL", "http://localhost:8090").rstrip("/")
AGENT_DVR_OBJECT_ID = os.getenv("AGENT_DVR_OBJECT_ID", "1")
AGENT_DVR_STREAM_URL = os.getenv("AGENT_DVR_STREAM_URL")
AGENT_DVR_IFRAME_URL = os.getenv("AGENT_DVR_IFRAME_URL")

DASHBOARD_FILE = PROJECT_ROOT / "web" / "dashboard.html"
LATEST_SUMMARY_INFO_FILE = os.getenv(
    "LATEST_SUMMARY_INFO_FILE",
    os.path.join(SUMMARY_DIR, "_latest_summary.json"),
)
