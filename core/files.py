import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import UploadFile


load_dotenv()

BASE_RESULT_DIR = os.getenv("BASE_RESULT_DIR", "/workspace/development/generated_data")
TEXT_DIR = os.getenv("TEXT_DIR", os.path.join(BASE_RESULT_DIR, "texts"))
VIDEO_DIR = os.getenv("VIDEO_DIR", os.path.join(BASE_RESULT_DIR, "videos"))
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "Asia/Seoul")
TEXT_INDEX_PREFIX = os.getenv("TEXT_INDEX_PREFIX", "_text_index")
LATEST_TEXT_INFO_FILE = os.getenv(
    "LATEST_TEXT_INFO_FILE",
    os.path.join(TEXT_DIR, "_latest_text.json"),
)

for directory in (TEXT_DIR, VIDEO_DIR):
    os.makedirs(directory, exist_ok=True)


def local_now() -> datetime:
    return datetime.now(ZoneInfo(LOCAL_TIMEZONE)).replace(tzinfo=None)


def timestamp_from_name(name: str) -> datetime:
    match = re.search(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", name)
    if not match:
        return local_now()
    return datetime.strptime(match.group(1), "%Y-%m-%d_%H-%M-%S")


def write_json_atomic(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp_path, target)


def read_indexed_file_info(index_path: str | Path) -> Optional[dict[str, Any]]:
    path = Path(index_path)
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    return info if isinstance(info, dict) else None


def file_info(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    modified_at = datetime.fromtimestamp(file_path.stat().st_mtime).astimezone()
    return {
        "name": file_path.name,
        "path": str(file_path),
        "modified_at": modified_at.isoformat(timespec="seconds"),
    }


def record_saved_text(text_path: str, source_name: str) -> None:
    file_path = Path(text_path)
    timestamp = timestamp_from_name(source_name)
    modified_at = datetime.fromtimestamp(file_path.stat().st_mtime, ZoneInfo(LOCAL_TIMEZONE))
    record = {
        "name": file_path.name,
        "path": str(file_path),
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "modified_at": modified_at.isoformat(timespec="seconds"),
    }
    index_path = Path(TEXT_DIR) / f"{TEXT_INDEX_PREFIX}_{timestamp:%Y-%m-%d}.jsonl"

    with index_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_json_atomic(LATEST_TEXT_INFO_FILE, record)


def save_uploaded_video(file: UploadFile, filename: str) -> str:
    safe_filename = Path(filename).name
    video_path = os.path.join(VIDEO_DIR, safe_filename)

    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return video_path


def save_analysis_text(text: str, filename: str) -> str:
    safe_stem = Path(filename).stem
    text_path = os.path.join(TEXT_DIR, f"{safe_stem}.txt")

    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)

    record_saved_text(text_path, safe_stem)
    return text_path
