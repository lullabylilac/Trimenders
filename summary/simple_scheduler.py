import io
import logging
import sys
from datetime import datetime as dt, timedelta, time as dt_time
from threading import Event

import pytz
from dotenv import load_dotenv

from summary.emailer import send_summary_email
from summary.worker import summarize_interval


logger = logging.getLogger(__name__)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")

load_dotenv()

INTERVAL_MIN = 3
KST = pytz.timezone("Asia/Seoul")
CUSTOM_TIME = None
_REAL_START_TIME = dt.now()


def get_now_kst():
    if CUSTOM_TIME is not None:
        elapsed = dt.now() - _REAL_START_TIME
        return CUSTOM_TIME + elapsed
    return dt.now(pytz.utc).astimezone(KST).replace(tzinfo=None)


def previous_interval(now_kst):
    today_start = dt.combine(now_kst.date(), dt_time(0, 0, 0))
    elapsed_sec = int((now_kst - today_start).total_seconds())
    current_idx = elapsed_sec // (INTERVAL_MIN * 60)
    end_range = today_start + timedelta(minutes=current_idx * INTERVAL_MIN)
    start_range = end_range - timedelta(minutes=INTERVAL_MIN)
    return start_range, end_range


def run_summary_for_range(start_range, end_range):
    result_file = summarize_interval(start_range, end_range, INTERVAL_MIN)
    if result_file:
        logger.info("요약 완료: %s", result_file)
        send_summary_email(result_file, start_range, end_range, get_now_kst)
    else:
        logger.warning("해당 구간의 분석 데이터가 없어 보고서를 생성하지 않았습니다.")


def run_initial_summary():
    now_kst = get_now_kst()
    start_range, end_range = previous_interval(now_kst)
    logger.info("[%s] 초기 진입 - 직전 마디 요약 프로세스 시작", now_kst.strftime("%H:%M:%S"))
    logger.info("분석 대상 구간: %s ~ %s", start_range.strftime("%H:%M:%S"), end_range.strftime("%H:%M:%S"))
    run_summary_for_range(start_range, end_range)


def run_daemon(stop_event: Event | None = None):
    stop_event = stop_event or Event()
    logger.info("CareNote 기본 요약 시스템 가동 중... (주기: %s분)", INTERVAL_MIN)
    if CUSTOM_TIME:
        logger.info("[타임머신 모드] 가상 시작 시각: %s", CUSTOM_TIME)

    run_initial_summary()
    now_kst = get_now_kst()
    _, target_end_time = previous_interval(now_kst)
    target_end_time += timedelta(minutes=INTERVAL_MIN)

    while not stop_event.is_set():
        now_kst = get_now_kst()
        if now_kst >= target_end_time:
            target_start_time = target_end_time - timedelta(minutes=INTERVAL_MIN)
            logger.info("[%s] %s분 정기 요약 시작", now_kst.strftime("%H:%M:%S"), INTERVAL_MIN)
            logger.info(
                "분석 대상 구간: %s ~ %s",
                target_start_time.strftime("%H:%M:%S"),
                target_end_time.strftime("%H:%M:%S"),
            )
            run_summary_for_range(target_start_time, target_end_time)
            target_end_time += timedelta(minutes=INTERVAL_MIN)
        else:
            target_start_time = target_end_time - timedelta(minutes=INTERVAL_MIN)
            status_msg = (
                f"대기 중... [다음 요약 예정 구간: "
                f"{target_start_time.strftime('%H:%M')} ~ {target_end_time.strftime('%H:%M')}]"
            )
            logger.debug(status_msg)
            stop_event.wait(1)

    logger.info("CareNote 기본 요약 시스템을 종료합니다.")
