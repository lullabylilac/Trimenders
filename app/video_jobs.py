import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from starlette.concurrency import run_in_threadpool

from app.config import EMAIL_ALERT_ENABLED, MODEL_TIMEOUT_SEC
from app.model_runtime import inference_lock, ml_models
from app.qwen import run_qwen_analysis
from core.files import file_info, save_analysis_text
from dashboard.state import add_event, set_alert, set_detection, set_latest_qwen, set_pipeline


logger = logging.getLogger(__name__)


def process_email_alert(analysis_text: str, request_id: str, text_path: Optional[str] = None) -> None:
    display_name = Path(text_path).name if text_path else request_id
    if not EMAIL_ALERT_ENABLED:
        logger.info("Email alert is disabled. Skipping %s", display_name)
        set_alert(
            "disabled",
            "알림 비활성화",
            "neutral",
            "EMAIL_ALERT_ENABLED=false 상태입니다.",
            request_id,
        )
        add_event("알림 처리 건너뜀", display_name, level="info", request_id=request_id)
        return

    try:
        set_alert(
            "processing",
            "알림 조건 확인중",
            "warning",
            "1차 감지 및 필요 시 Claude 2차 확인을 실행합니다.",
            request_id,
        )
        add_event("알림 조건 확인중", display_name, level="info", request_id=request_id)

        from detection.pipeline import process_text_content

        result = process_text_content(
            analysis_text,
            source_name=display_name,
            file_path=text_path,
        )
        logger.info("Email alert check finished for %s: %s", display_name, result)

        if isinstance(result, dict):
            stage1_detected = bool(result.get("stage1_detected"))
            verdict = result.get("stage2_verdict") or "NORMAL"
            reason = result.get("reason") or ""
            email_sent = bool(result.get("email_sent"))

            if verdict == "FALL":
                set_detection("fall_confirmed", "최종 감지: 낙상 감지", "danger", reason, request_id)
                set_alert(
                    "sent" if email_sent else "detected",
                    "긴급 알림 발송완료" if email_sent else "긴급 알림 필요",
                    "danger",
                    reason,
                    request_id,
                )
                add_event("최종 감지: 낙상 감지", reason, level="danger", request_id=request_id)
            elif verdict == "CAUTION":
                set_detection("caution", "최종 감지: 주의 필요", "warning", reason, request_id)
                set_alert("checked", "알림 조건 확인완료", "warning", reason, request_id)
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
                set_alert("checked", "알림 조건 없음", "success", "긴급 알림 발송 조건이 없습니다.", request_id)
                add_event("1차 감지: 낙상 감지안됨", "알림 조건 없음", level="success", request_id=request_id)
        else:
            set_alert("checked", "알림 처리 완료", "success", "텍스트 검사가 완료되었습니다.", request_id)
            add_event("알림 처리 완료", display_name, level="success", request_id=request_id)
    except Exception:
        logger.exception("Email alert processing failed for %s", display_name)
        set_alert("error", "알림 처리 실패", "danger", display_name, request_id)
        add_event("알림 처리 실패", display_name, level="danger", request_id=request_id)


def delete_uploaded_video(video_path: Optional[str]) -> bool:
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
            set_pipeline("processing", "Qwen3-VL 텍스트 생성중", "카메라 영상을 분석하고 있습니다.", request_id)
            add_event("Qwen3-VL 텍스트 생성중", video_filename, level="info", request_id=request_id)

            try:
                description = await asyncio.wait_for(
                    run_in_threadpool(
                        run_qwen_analysis,
                        video_path,
                        ml_models["processor"],
                        ml_models["llm"],
                    ),
                    timeout=MODEL_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                logger.error("GPU 분석 타임아웃 (%s초 초과): %s", MODEL_TIMEOUT_SEC, video_filename)
                raise RuntimeError("모델 추론 시간이 너무 오래 걸려 강제 중단되었습니다.")

        text_path = await run_in_threadpool(save_analysis_text, description, request_id)
        text_info = file_info(text_path)

        set_latest_qwen(text_info, request_id)
        set_pipeline("complete", "Qwen3-VL 텍스트 생성완료", Path(text_path).name, request_id)
        add_event("Qwen3-VL 텍스트 생성완료", Path(text_path).name, level="success", request_id=request_id)

        set_detection("checking", "1차 감지 확인중", "warning", "1차 감지 모델로 확인하고 있습니다.", request_id)
        await run_in_threadpool(process_email_alert, description, request_id, text_path)

    except Exception:
        logger.exception("Video analysis failed")
        set_pipeline("error", "분석 실패", "영상 분석 중 문제가 발생했습니다.", request_id)
        add_event("분석 실패", original_name, level="danger", request_id=request_id)

    finally:
        video_deleted = await run_in_threadpool(delete_uploaded_video, video_path)
        if video_deleted:
            add_event("임시 영상 삭제완료", video_filename, level="success", request_id=request_id)
