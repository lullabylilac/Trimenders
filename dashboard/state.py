from zoneinfo import ZoneInfo

import json
import os
import re
import tempfile
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


BASE_RESULT_DIR = os.getenv("BASE_RESULT_DIR", "/workspace/development/generated_data")
DASHBOARD_STATE_FILE = Path(
    os.getenv(
        "DASHBOARD_STATE_FILE",
        os.path.join(BASE_RESULT_DIR, "status", "dashboard_state.json"),
    )
)
DASHBOARD_CONFIG_FILE = Path(
    os.getenv(
        "DASHBOARD_CONFIG_FILE",
        os.path.join(BASE_RESULT_DIR, "status", "dashboard_config.json"),
    )
)
MAX_EVENTS = int(os.getenv("DASHBOARD_MAX_EVENTS", "100"))
DEFAULT_RECEIVER_EMAIL = os.environ.get("JANG_EMAIL")
EMAIL_PATTERN = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")

_lock = threading.RLock()

def now_iso_kst() -> str:
    """항상 한국 표준시(KST, UTC+9) 기준의 ISO 포맷 시각을 반환합니다."""
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


# def now_iso() -> str:
#     return datetime.now().astimezone().isoformat(timespec="seconds")

# 기존의 now_iso 대신 이 함수를 사용하도록 통일하면 편합니다.
def now_iso() -> str:
    return now_iso_kst()


def default_state() -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "pipeline": {
            "status": "idle",
            "label": "대기중",
            "message": "분석 요청을 기다리고 있습니다.",
            "request_id": None,
            "updated_at": timestamp,
        },
        "detection": {
            "status": "unknown",
            "label": "1차 감지: 대기중",
            "level": "neutral",
            "message": "아직 분석 결과가 없습니다.",
            "request_id": None,
            "updated_at": timestamp,
        },
        "alert": {
            "status": "idle",
            "label": "알림 대기중",
            "level": "neutral",
            "message": "위험 상황 감지 시 알림 검사를 실행합니다.",
            "request_id": None,
            "updated_at": timestamp,
        },
        "summary": {
            "status": "waiting",
            "label": "요약보고서 대기중",
            "level": "neutral",
            "message": "정기 요약 실행을 기다리고 있습니다.",
            "latest_file": None,
            "updated_at": timestamp,
        },
        "latest_qwen": None,
        "events": [],
    }


def default_config() -> dict[str, Any]:
    return {
        "receiver_email": DEFAULT_RECEIVER_EMAIL,
        "updated_at": now_iso(),
    }


def normalize_receiver_email(value: str) -> str:
    emails = [email.strip() for email in value.split(",") if email.strip()]
    if not emails:
        raise ValueError("수신자 이메일을 입력해주세요.")

    invalid = [email for email in emails if not EMAIL_PATTERN.match(email)]
    if invalid:
        raise ValueError(f"이메일 형식이 올바르지 않습니다: {', '.join(invalid)}")

    return ",".join(emails)


def parse_receiver_emails(value: str) -> list[str]:
    return normalize_receiver_email(value).split(",")


def _merge_defaults(state: dict[str, Any]) -> dict[str, Any]:
    merged = default_state()
    for key, value in state.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def _merge_config_defaults(config: dict[str, Any]) -> dict[str, Any]:
    merged = default_config()
    merged.update(config)
    return merged


def read_state() -> dict[str, Any]:
    with _lock:
        if not DASHBOARD_STATE_FILE.exists():
            return default_state()

        try:
            with DASHBOARD_STATE_FILE.open("r", encoding="utf-8") as f:
                return _merge_defaults(json.load(f))
        except Exception:
            return default_state()


def read_config() -> dict[str, Any]:
    with _lock:
        if not DASHBOARD_CONFIG_FILE.exists():
            return default_config()

        try:
            with DASHBOARD_CONFIG_FILE.open("r", encoding="utf-8") as f:
                return _merge_config_defaults(json.load(f))
        except Exception:
            return default_config()


def write_state(state: dict[str, Any]) -> None:
    DASHBOARD_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = _merge_defaults(state)
    state["events"] = list(state.get("events", []))[:MAX_EVENTS]

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(DASHBOARD_STATE_FILE.parent),
        prefix=".dashboard_state_",
        suffix=".tmp",
    ) as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        temp_name = f.name

    os.replace(temp_name, DASHBOARD_STATE_FILE)


def write_config(config: dict[str, Any]) -> None:
    DASHBOARD_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    config = _merge_config_defaults(config)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(DASHBOARD_CONFIG_FILE.parent),
        prefix=".dashboard_config_",
        suffix=".tmp",
    ) as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        temp_name = f.name

    os.replace(temp_name, DASHBOARD_CONFIG_FILE)


def get_receiver_email() -> str:
    return read_config().get("receiver_email") or DEFAULT_RECEIVER_EMAIL


def get_receiver_emails() -> list[str]:
    return parse_receiver_emails(get_receiver_email())


def format_receiver_emails(emails: Optional[list[str]] = None) -> str:
    return ", ".join(emails if emails is not None else get_receiver_emails())


def set_receiver_email(receiver_email: str) -> dict[str, Any]:
    normalized = normalize_receiver_email(receiver_email)

    with _lock:
        config = read_config()
        config["receiver_email"] = normalized
        config["updated_at"] = now_iso()
        write_config(config)

    add_event("수신자 이메일 변경", normalized, level="info")
    return config


def reset_receiver_email() -> dict[str, Any]:
    current_time = now_iso()
    with _lock:
        config = read_config()
        config["receiver_email"] = DEFAULT_RECEIVER_EMAIL
        config["updated_at"] = now_iso()

        write_config(config)

    add_event("수신자 이메일 초기화", DEFAULT_RECEIVER_EMAIL, level="info")
    return config


def mutate_state(mutator) -> dict[str, Any]:
    with _lock:
        state = read_state()
        mutator(state)
        write_state(state)
        return deepcopy(state)


def update_section(section: str, **fields: Any) -> None:
    def apply(state: dict[str, Any]) -> None:
        current = state.setdefault(section, {})
        current.update(fields)
        current["updated_at"] = now_iso()

    mutate_state(apply)


def add_event(
    title: str,
    message: str = "",
    level: str = "info",
    request_id: Optional[str] = None,
) -> None:
    def apply(state: dict[str, Any]) -> None:
        events = state.setdefault("events", [])
        events.insert(
            0,
            {
                "time": now_iso(),
                "title": title,
                "message": message,
                "level": level,
                "request_id": request_id,
            },
        )
        del events[MAX_EVENTS:]

    mutate_state(apply)


def set_pipeline(
    status: str,
    label: str,
    message: str = "",
    request_id: Optional[str] = None,
) -> None:
    update_section(
        "pipeline",
        status=status,
        label=label,
        message=message,
        request_id=request_id,
    )


def set_detection(
    status: str,
    label: str,
    level: str,
    message: str = "",
    request_id: Optional[str] = None,
) -> None:
    update_section(
        "detection",
        status=status,
        label=label,
        level=level,
        message=message,
        request_id=request_id,
    )


def set_alert(
    status: str,
    label: str,
    level: str,
    message: str = "",
    request_id: Optional[str] = None,
) -> None:
    update_section(
        "alert",
        status=status,
        label=label,
        level=level,
        message=message,
        request_id=request_id,
    )


def set_summary(
    status: str,
    label: str,
    level: str,
    message: str = "",
    latest_file: Optional[dict[str, Any]] = None,
) -> None:
    fields: dict[str, Any] = {
        "status": status,
        "label": label,
        "level": level,
        "message": message,
    }
    if latest_file is not None:
        fields["latest_file"] = latest_file
    update_section("summary", **fields)


def set_latest_qwen(file_info: dict[str, Any], request_id: Optional[str] = None) -> None:
    def apply(state: dict[str, Any]) -> None:
        state["latest_qwen"] = {
            **file_info,
            "request_id": request_id,
            "updated_at": now_iso(),
        }

    mutate_state(apply)
