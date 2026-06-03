import os
import sys
import io
import time
import smtplib
from datetime import datetime as dt, timedelta, time as dt_time
import pytz
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

from summary_worker import summarize_interval, SUMMARY_DIR

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

load_dotenv()

# ============================================================
# [설정]
# ============================================================
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("JANG_EMAIL")

INTERVAL_MIN = 3
KST = pytz.timezone('Asia/Seoul')

# ============================================================
# 🕒 [타임머신 설정 (테스트 모드)]
# ============================================================
# CUSTOM_TIME을 None으로 두면 '실제 KST 현재 시각'으로 작동합니다.
CUSTOM_TIME = None
# CUSTOM_TIME = dt(2026, 5, 12, 21, 28, 0)
_REAL_START_TIME = dt.now()

def get_now_kst():
    if CUSTOM_TIME is not None:
        elapsed = dt.now() - _REAL_START_TIME
        return CUSTOM_TIME + elapsed
    else:
        return dt.now(pytz.utc).astimezone(KST).replace(tzinfo=None)

def send_summary_email(file_name, start_time, end_time):
    file_path = os.path.join(SUMMARY_DIR, file_name)
    try:
        now_time = get_now_kst().strftime("%Y-%m-%d %H:%M:%S")
        time_str = f"{start_time.strftime('%H:%M')} ~ {end_time.strftime('%H:%M')}"
        subject = f"📋 [CareNote] 정기 활동 요약 보고서 ({time_str})"

        with open(file_path, 'r', encoding='utf-8') as f:
            summary_content = f.read()

        body = f"""안녕하세요, CareNote 입니다.
요청하신 ({time_str}) 시간대 어르신 활동 요약 보고서를 보내드립니다.

------------------------------------------------------------
{summary_content}
------------------------------------------------------------

* 상세 내용은 첨부된 텍스트 파일({file_name})을 통해서도 확인하실 수 있습니다.

- 어르신의 하루를 읽다, CareNote 팀 드림.
"""
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                attachment = MIMEApplication(f.read(), _subtype="txt")
                attachment.add_header('Content-Disposition', 'attachment', filename=file_name)
                msg.attach(attachment)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"   📧 [이메일] 요약 보고서 발송 완료! ({file_name})")
        
    except Exception as e:
        print(f"   ❌ [에러] 이메일 발송 실패: {e}")

def run_initial_summary():
    """스크립트 실행 시 직전에 완료된 마디를 즉시 한 번 요약합니다."""
    now_kst = get_now_kst()
    today_start = dt.combine(now_kst.date(), dt_time(0, 0, 0))
    elapsed_sec = int((now_kst - today_start).total_seconds())
    current_idx = elapsed_sec // (INTERVAL_MIN * 60)
    
    end_range = today_start + timedelta(minutes=current_idx * INTERVAL_MIN)
    start_range = end_range - timedelta(minutes=INTERVAL_MIN)

    print(f"\n[{now_kst.strftime('%H:%M:%S')}] 초기 진입 - 직전 마디 요약 프로세스 시작...")
    print(f"🔍 분석 대상 구간: {start_range.strftime('%H:%M:%S')} ~ {end_range.strftime('%H:%M:%S')}")
    
    result_file = summarize_interval(start_range, end_range, INTERVAL_MIN)
    if result_file:
        print(f"   ✅ 요약 완료: {result_file}")
        send_summary_email(result_file, start_range, end_range)
    else:
        print("   ⚪ 해당 구간에 분석 데이터가 없어 보고서를 생성하지 않았습니다.")

def run_daemon():
    print(f"\n🚀 CareNote 요약 시스템 가동 중... (주기: {INTERVAL_MIN}분)")
    if CUSTOM_TIME:
        print(f"🛠️ [타임머신 모드] 가상 시작 시각: {CUSTOM_TIME}")
        
    # 1. 켜자마자 과거 구간 즉시 1회 요약
    run_initial_summary()
    
    # 2. 다음 요약이 실행될 '정각' 타겟 계산 (예: 21:20이면 타겟은 21:21:00)
    now_kst = get_now_kst()
    today_start = dt.combine(now_kst.date(), dt_time(0, 0, 0))
    elapsed_sec = int((now_kst - today_start).total_seconds())
    current_idx = elapsed_sec // (INTERVAL_MIN * 60)
    
    target_end_time = today_start + timedelta(minutes=(current_idx + 1) * INTERVAL_MIN)

    while True:
        now_kst = get_now_kst()
        
        # [실행 타이밍 도달] (예: 가상 시간이 21:21:00이 됨)
        if now_kst >= target_end_time:
            target_start_time = target_end_time - timedelta(minutes=INTERVAL_MIN)
            
            print(f"\n[{now_kst.strftime('%H:%M:%S')}] {INTERVAL_MIN}분 정기 요약 시작...")
            print(f"🔍 분석 대상 구간: {target_start_time.strftime('%H:%M:%S')} ~ {target_end_time.strftime('%H:%M:%S')}")
            
            result_file = summarize_interval(target_start_time, target_end_time, INTERVAL_MIN)
            if result_file:
                print(f"   ✅ 요약 완료: {result_file}")
                send_summary_email(result_file, target_start_time, target_end_time)
            else:
                print("   ⚪ 해당 구간에 분석 데이터가 없어 보고서를 생성하지 않았습니다.")
            
            # 다음 타겟 시간으로 갱신 (예: 21:21 -> 21:24)
            target_end_time += timedelta(minutes=INTERVAL_MIN)
        
        # [대기 상태] 
        else:
            target_start_time = target_end_time - timedelta(minutes=INTERVAL_MIN)
            status_msg = f"\r⏳ 대기 중... [다음 요약 예정 구간: {target_start_time.strftime('%H:%M')} ~ {target_end_time.strftime('%H:%M')}]"
            sys.stdout.write(status_msg)
            sys.stdout.flush()
            time.sleep(1)

if __name__ == "__main__":
    run_daemon()