import datetime
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from dotenv import load_dotenv

from dashboard.state import get_receiver_email


load_dotenv()
logger = logging.getLogger(__name__)

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")


def receiver_email() -> str:
    return get_receiver_email() or os.environ.get("JANG_EMAIL") or ""


def send_gmail_alert(verdict, reason, target_sentence, file_path=None, file_name=None):
    try:
        kst = datetime.timezone(datetime.timedelta(hours=9))
        now_time = datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
        filename = file_name or (os.path.basename(file_path) if file_path else "realtime_analysis.txt")
        subject = f"🚨 [CareNote] 긴급 낙상 감지: ({now_time})"

        body = f"""
시스템에서 낙상 사고가 감지되었습니다. 원본 영상을 확인 바랍니다.

[감지 시간]: {now_time}
[분석 파일명]: {filename}
[AI 판정]: {verdict}
[상세 이유]: {reason}
[감지 근거]: {target_sentence}

* 상세 내용은 첨부된 텍스트 파일을 통해서도 확인하실 수 있습니다.

- 어르신의 하루를 읽다, CareNote 팀 드림.
"""

        msg = MIMEMultipart()
        msg["From"] = formataddr(("CareNote", SENDER_EMAIL))
        msg["To"] = receiver_email()
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="txt")
                attachment.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(attachment)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        logger.info("Gmail 낙상 알림 발송 완료: %s", filename)
        return True
    except Exception as exc:
        logger.exception("낙상 알림 메일 발송 실패: %s", exc)
        return False
