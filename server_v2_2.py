import os
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
import asyncio
from concurrent.futures import ThreadPoolExecutor
gpu_executor = ThreadPoolExecutor(max_workers=1)
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlencode
from uuid import uuid4


from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from transformers import AutoProcessor
from vllm import LLM

from carenote_dashboard import (
    add_event,
    get_receiver_email,
    read_config,
    read_state,
    reset_receiver_email,
    set_alert,
    set_detection,
    set_latest_qwen,
    set_pipeline,
    set_receiver_email,
    set_summary,
)
from utils import TEXT_DIR, save_analysis_text, save_uploaded_video, run_qwen_analysis
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

CHECKPOINT_PATH = os.getenv("CHECKPOINT_PATH", "/workspace/models/qwen3-vl-8b-instruct-fp8")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(1024 * 1024 * 1024)))
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
EMAIL_ALERT_ENABLED = os.getenv("EMAIL_ALERT_ENABLED", "true").lower() == "true"
BASE_RESULT_DIR = os.getenv("BASE_RESULT_DIR", "/workspace/development/generated_data")
SUMMARY_DIR = os.getenv("SUMMARY_DIR", os.path.join(BASE_RESULT_DIR, "summaries"))
AGENT_DVR_BASE_URL = os.getenv("AGENT_DVR_BASE_URL", "http://localhost:8090").rstrip("/")
AGENT_DVR_OBJECT_ID = os.getenv("AGENT_DVR_OBJECT_ID", "2")
AGENT_DVR_STREAM_URL = os.getenv("AGENT_DVR_STREAM_URL")
AGENT_DVR_IFRAME_URL = os.getenv("AGENT_DVR_IFRAME_URL")
DASHBOARD_FILE = Path(__file__).with_name("dashboard.html")

ml_models = {}
inference_lock = asyncio.Lock()


class DashboardSettingsUpdate(BaseModel):
    receiver_email: str


def file_info(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    modified_at = datetime.fromtimestamp(file_path.stat().st_mtime).astimezone()
    return {
        "name": file_path.name,
        "path": str(file_path),
        "modified_at": modified_at.isoformat(timespec="seconds"),
    }


def latest_file_info(directories: Iterable[str | Path]) -> Optional[dict[str, Any]]:
    candidates: list[Path] = []
    for directory in directories:
        directory_path = Path(directory)
        if not directory_path.exists():
            continue
        candidates.extend(
            path
            for path in directory_path.glob("*.txt")
            if path.is_file() and not path.name.endswith(".lock")
        )

    if not candidates:
        return None

    return file_info(max(candidates, key=lambda path: path.stat().st_mtime))


def summary_directories() -> list[Path]:
    server_dir = Path(__file__).resolve().parent
    candidates = [
        Path(SUMMARY_DIR),
        Path(BASE_RESULT_DIR) / "summaries",
        server_dir / "summaries",
        # Path("/root/development/generated_data/summaries"),
        Path("/workspace/development/generated_data/summaries"),
    ]
    unique: list[Path] = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def build_agent_dvr_urls() -> dict[str, str]:
    stream_url = AGENT_DVR_STREAM_URL
    if not stream_url:
        query = urlencode(
            {
                "oid": AGENT_DVR_OBJECT_ID,
                "size": "1280x720",
                "maintainAR": "true",
            }
        )
        stream_url = f"{AGENT_DVR_BASE_URL}/video.mjpg?{query}"

    iframe_url = AGENT_DVR_IFRAME_URL
    if not iframe_url:
        query = urlencode(
            {
                "start": "Live",
                "ot": "2",
                "oid": AGENT_DVR_OBJECT_ID,
                "max": "true",
                "mini": "true",
            }
        )
        iframe_url = f"{AGENT_DVR_BASE_URL}/?{query}"

    return {
        "stream_url": stream_url,
        "iframe_url": iframe_url,
        "object_id": AGENT_DVR_OBJECT_ID,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading processor from %s", CHECKPOINT_PATH)
    ml_models["processor"] = AutoProcessor.from_pretrained(
        CHECKPOINT_PATH,
        trust_remote_code=True,
    )

    logger.info("Loading vLLM engine from %s", CHECKPOINT_PATH)
    ml_models["llm"] = LLM(
        model=CHECKPOINT_PATH,
        trust_remote_code=True,
        gpu_memory_utilization=float(os.getenv("GPU_MEMORY_UTILIZATION", "0.8")),
        max_model_len=int(os.getenv("MAX_MODEL_LEN", "32768")),
        tensor_parallel_size=int(os.getenv("TENSOR_PARALLEL_SIZE", "1")),
        enforce_eager=os.getenv("ENFORCE_EAGER", "true").lower() == "true",
    )

    logger.info("Server is ready")
    try:
        yield
    finally:
        ml_models.clear()
        logger.info("Model references cleared")


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": "processor" in ml_models and "llm" in ml_models,
    }


@app.get("/dashboard")
async def dashboard():
    if not DASHBOARD_FILE.exists():
        raise HTTPException(status_code=404, detail="dashboard.html was not found.")
    return FileResponse(DASHBOARD_FILE)


@app.get("/api/dashboard/status")
async def dashboard_status():
    state = read_state()
    config = read_config()
    latest_qwen = latest_file_info([TEXT_DIR])
    latest_summary = latest_file_info(summary_directories())

    if latest_summary:
        current = state.get("summary", {}).get("latest_file")
        current_name = current.get("name") if isinstance(current, dict) else None
        if current_name != latest_summary["name"]:
            set_summary(
                "complete",
                "요약보고서 생성완료",
                "success",
                latest_summary["name"],
                latest_summary,
            )
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


@app.get("/api/dashboard/settings")
async def dashboard_settings():
    config = read_config()
    return {
        "receiver_email": config.get("receiver_email") or get_receiver_email(),
        "updated_at": config.get("updated_at"),
    }


@app.post("/api/dashboard/settings")
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


@app.post("/api/dashboard/settings/reset")
async def reset_dashboard_settings():
    config = reset_receiver_email()
    return {
        "status": "success",
        "receiver_email": config["receiver_email"],
        "updated_at": config["updated_at"],
    }


def process_email_alert(text_path: str) -> None:
    """Analyze one saved text result and send an email alert if needed."""
    request_id = Path(text_path).stem
    if not EMAIL_ALERT_ENABLED:
        logger.info("Email alert is disabled. Skipping %s", text_path)
        set_alert(
            "disabled",
            "알림 비활성화",
            "neutral",
            "EMAIL_ALERT_ENABLED=false 상태입니다.",
            request_id,
        )
        add_event("알림 처리 건너뜀", Path(text_path).name, level="info", request_id=request_id)
        return

    try:
        from test2_email_file import process_text_file

        set_alert(
            "processing",
            "알림 조건 확인중",
            "warning",
            "1차 감지 및 필요 시 Claude 2차 확인을 실행합니다.",
            request_id,
        )
        add_event("알림 조건 확인중", Path(text_path).name, level="info", request_id=request_id)
        result = process_text_file(text_path)
        logger.info("Email alert check finished for %s: %s", text_path, result)

        if isinstance(result, dict):
            stage1_detected = bool(result.get("stage1_detected"))
            verdict = result.get("stage2_verdict") or "NORMAL"
            reason = result.get("reason") or ""
            email_sent = bool(result.get("email_sent"))

            if verdict == "FALL":
                set_detection(
                    "fall_confirmed",
                    "최종 감지: 낙상 감지",
                    "danger",
                    reason,
                    request_id,
                )
                set_alert(
                    "sent" if email_sent else "detected",
                    "긴급 알림 발송완료" if email_sent else "긴급 알림 필요",
                    "danger",
                    reason,
                    request_id,
                )
                add_event("최종 감지: 낙상 감지", reason, level="danger", request_id=request_id)
            elif verdict == "CAUTION":
                set_detection(
                    "caution",
                    "최종 감지: 주의 필요",
                    "warning",
                    reason,
                    request_id,
                )
                set_alert(
                    "checked",
                    "알림 조건 확인완료",
                    "warning",
                    reason,
                    request_id,
                )
                add_event("최종 감지: 주의 필요", reason, level="warning", request_id=request_id)
            elif stage1_detected:
                set_alert(
                    "checked",
                    "2차 확인: 낙상 아님",
                    "success",
                    reason or "Claude 확인 결과 낙상으로 판단되지 않았습니다.",
                    request_id,
                )
                add_event("2차 확인: 낙상 아님", reason, level="success", request_id=request_id)
            else:
                set_detection(
                    "no_fall",
                    "1차 감지: 낙상 감지안됨",
                    "success",
                    "1차 검사에서 위험 문장이 발견되지 않았습니다.",
                    request_id,
                )
                set_alert(
                    "checked",
                    "알림 조건 없음",
                    "success",
                    "긴급 알림 발송 조건이 없습니다.",
                    request_id,
                )
                add_event("1차 감지: 낙상 감지안됨", "알림 조건 없음", level="success", request_id=request_id)
        else:
            set_alert(
                "checked",
                "알림 처리 완료",
                "success",
                "텍스트 파일 검사가 완료되었습니다.",
                request_id,
            )
            add_event("알림 처리 완료", Path(text_path).name, level="success", request_id=request_id)
    except Exception:
        logger.exception("Email alert processing failed for %s", text_path)
        set_alert(
            "error",
            "알림 처리 실패",
            "danger",
            Path(text_path).name,
            request_id,
        )
        add_event("알림 처리 실패", Path(text_path).name, level="danger", request_id=request_id)


def delete_uploaded_video(video_path: Optional[str]) -> bool:
    """Delete the uploaded video file after analysis."""
    if not video_path:
        return True

    try:
        os.remove(video_path)
        logger.info("Deleted uploaded video: %s", video_path)
        return True
    except FileNotFoundError:
        logger.info("Uploaded video already deleted: %s", video_path)
        return True
    except Exception:
        logger.exception("Failed to delete uploaded video: %s", video_path)
        return False

async def analyze_video_job(
    video_path: str,
    request_id: str,
    original_name: str,
    video_filename: str,
) -> None:
    try:
        async with inference_lock:
            set_pipeline(
                "processing",
                "Qwen3-VL 텍스트 생성중",
                "카메라 영상을 분석하고 있습니다.",
                request_id,
            )
            add_event("Qwen3-VL 텍스트 생성중", video_filename, level="info", request_id=request_id)

# [수정됨] GPU 데드락을 방지하기 위해 60초 타임아웃 적용
            try:
                description = await asyncio.wait_for(
                    run_in_threadpool(
                        run_qwen_analysis,
                        video_path,
                        ml_models["processor"],
                        ml_models["llm"],
                    ),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                logger.error(f"GPU 분석 타임아웃 (60초 초과): {video_filename}")
                raise RuntimeError("모델 추론 시간이 너무 오래 걸려 강제 중단되었습니다.")

        text_path = await run_in_threadpool(save_analysis_text, description, request_id)
        text_info = file_info(text_path)

        set_latest_qwen(text_info, request_id)
        set_pipeline("complete", "Qwen3-VL 텍스트 생성완료", Path(text_path).name, request_id)
        add_event("Qwen3-VL 텍스트 생성완료", Path(text_path).name, level="success", request_id=request_id)

        set_detection(
            "checking",
            "1차 감지 확인중",
            "warning",
            "1차 감지 모델로 확인하고 있습니다.",
            request_id,
        )

        await run_in_threadpool(process_email_alert, text_path)

    except Exception:
        logger.exception("Video analysis failed")
        set_pipeline("error", "분석 실패", "영상 분석 중 문제가 발생했습니다.", request_id)
        add_event("분석 실패", original_name, level="danger", request_id=request_id)

    finally:
        video_deleted = await run_in_threadpool(delete_uploaded_video, video_path)
        if video_deleted:
            add_event("임시 영상 삭제완료", video_filename, level="success", request_id=request_id)


@app.post("/analyze-video/", status_code=202)
async def analyze_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if inference_lock.locked():
        logger.warning(f"GPU가 사용 중입니다. 실시간성을 위해 {file.filename} 영상을 폐기합니다.")
        return {
            "status": "dropped",
            "message": "현재 이전 영상을 분석 중이므로 이번 영상은 건너뜁니다."
        }
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported video file format.")

    content_length = file.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded video is too large.")

    if "processor" not in ml_models or "llm" not in ml_models:
        raise HTTPException(status_code=503, detail="Model is not ready.")

    safe_stem = Path(original_name).stem or "uploaded_video"
    request_id = f"{safe_stem}_{uuid4().hex[:8]}"
    video_filename = f"{request_id}{suffix}"
    video_path: Optional[str] = None
    scheduled = False

    try:
        set_pipeline("queued", "영상 업로드 수신", "분석 대기열에 추가했습니다.", request_id)
        add_event("영상 업로드 수신", original_name, level="info", request_id=request_id)

        video_path = await run_in_threadpool(save_uploaded_video, file, video_filename)

        background_tasks.add_task(
            analyze_video_job,
            video_path,
            request_id,
            original_name,
            video_filename,
        )
        scheduled = True

        return {
            "status": "queued",
            "id": request_id,
            "message": "영상 업로드 완료. 분석은 백그라운드에서 진행됩니다.",
        }

    finally:
        await file.close()
        if video_path and not scheduled:
            await run_in_threadpool(delete_uploaded_video, video_path)