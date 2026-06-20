import os
import smtplib
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from app.config import SUMMARY_DIR


load_dotenv()
logger = logging.getLogger(__name__)

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("JANG_EMAIL")


def send_summary_email(file_name, start_time, end_time, now_provider):
    file_path = os.path.join(SUMMARY_DIR, file_name)
    try:
        now_time = now_provider().strftime("%Y-%m-%d %H:%M:%S")
        time_str = f"{start_time.strftime('%H:%M')} ~ {end_time.strftime('%H:%M')}"
        subject = f"📋 [CareNote] 정기 행동 요약 보고서 ({time_str})"

        with open(file_path, "r", encoding="utf-8") as f:
            summary_content = f.read()

        body = f"""안녕하세요. CareNote 입니다.
요청하신 ({time_str}) 시간대 어르신 행동 요약 보고서를 보내드립니다.

------------------------------------------------------------
{summary_content}
------------------------------------------------------------

* 상세 내용은 첨부된 텍스트 파일({file_name})에서도 확인하실 수 있습니다.

- 어르신의 하루를 읽다, CareNote 팀 드림.
"""

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="txt")
                attachment.add_header("Content-Disposition", "attachment", filename=file_name)
                msg.attach(attachment)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        logger.info("이메일 요약 보고서 발송 완료: %s", file_name)
    except Exception as exc:
        logger.exception("이메일 발송 실패: %s", exc)
