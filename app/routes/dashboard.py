from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import DASHBOARD_FILE, LATEST_SUMMARY_INFO_FILE
from app.dvr import build_agent_dvr_urls
from app.model_runtime import ml_models
from core.files import LATEST_TEXT_INFO_FILE, read_indexed_file_info
from dashboard.state import (
    add_event,
    get_receiver_email,
    read_config,
    read_state,
    reset_receiver_email,
    set_receiver_email,
    set_summary,
)


router = APIRouter()


class DashboardSettingsUpdate(BaseModel):
    receiver_email: str


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": "processor" in ml_models and "llm" in ml_models,
    }


@router.get("/dashboard")
async def dashboard():
    if not DASHBOARD_FILE.exists():
        raise HTTPException(status_code=404, detail="dashboard.html was not found.")
    return FileResponse(DASHBOARD_FILE)


@router.get("/api/dashboard/status")
async def dashboard_status():
    state = read_state()
    config = read_config()
    latest_qwen = read_indexed_file_info(LATEST_TEXT_INFO_FILE) or state.get("latest_qwen")
    latest_summary = read_indexed_file_info(LATEST_SUMMARY_INFO_FILE)

    if latest_summary:
        current = state.get("summary", {}).get("latest_file")
        current_name = current.get("name") if isinstance(current, dict) else None
        if current_name != latest_summary["name"]:
            set_summary("complete", "요약보고서 생성완료", "success", latest_summary["name"], latest_summary)
            add_event("요약보고서 생성완료", latest_summary["name"], level="success")
            state = read_state()

    return {
        "model_loaded": "processor" in ml_models and "llm" in ml_models,
        "agent_dvr": build_agent_dvr_urls(),
        "pipeline": state["pipeline"],
        "detection": state["detection"],
        "alert": state["alert"],
        "summary": state["summary"],
        "latest_qwen": latest_qwen or state.get("latest_qwen"),
        "settings": {
            "receiver_email": config.get("receiver_email") or get_receiver_email(),
            "updated_at": config.get("updated_at"),
        },
        "events": state.get("events", [])[:50],
    }


@router.get("/api/dashboard/settings")
async def dashboard_settings():
    config = read_config()
    return {
        "receiver_email": config.get("receiver_email") or get_receiver_email(),
        "updated_at": config.get("updated_at"),
    }


@router.post("/api/dashboard/settings")
async def update_dashboard_settings(settings: DashboardSettingsUpdate):
    try:
        config = set_receiver_email(settings.receiver_email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "success",
        "receiver_email": config["receiver_email"],
        "updated_at": config["updated_at"],
    }


@router.post("/api/dashboard/settings/reset")
async def reset_dashboard_settings():
    config = reset_receiver_email()
    return {
        "status": "success",
        "receiver_email": config["receiver_email"],
        "updated_at": config["updated_at"],
    }
