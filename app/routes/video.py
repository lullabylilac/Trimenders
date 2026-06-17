from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import ALLOWED_VIDEO_EXTENSIONS, MAX_UPLOAD_BYTES
from app.model_runtime import inference_lock, ml_models
from app.video_jobs import analyze_video_job, delete_uploaded_video
from core.files import save_uploaded_video
from dashboard.state import add_event, set_pipeline


router = APIRouter()


@router.post("/analyze-video/", status_code=202)
async def analyze_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if inference_lock.locked():
        return {
            "status": "dropped",
            "message": "현재 이전 영상을 분석 중이므로 이번 영상은 건너뜁니다.",
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
        background_tasks.add_task(analyze_video_job, video_path, request_id, original_name, video_filename)
        scheduled = True

        return {
            "status": "queued",
            "id": request_id,
            "message": "영상 업로드 완료. 분석은 백그라운드에서 진행합니다.",
        }
    finally:
        await file.close()
        if video_path and not scheduled:
            await run_in_threadpool(delete_uploaded_video, video_path)
