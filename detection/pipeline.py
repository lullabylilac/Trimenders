import logging
import os
import re
import sys

from detection.classifier import embedding_classify
from detection.claude_review import claude_analyze
from detection.emailer import send_gmail_alert


logger = logging.getLogger(__name__)

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")


def split_sentences(full_text: str) -> list[str]:
    sentences = re.split(r"[\n\.]+", full_text)
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 5]


def process_text_content(full_text: str, source_name: str = "realtime_analysis.txt", file_path: str | None = None):
    logger.info("텍스트 분석 시작: %s", source_name)

    needs_claude_check = False
    detected_sentence = ""
    logger.info("1차 검사: 문장 단위 위험 정황 스캔 중")

    for sentence in split_sentences(full_text):
        emb = embedding_classify(sentence)
        if emb["detected"]:
            needs_claude_check = True
            detected_sentence = sentence
            logger.warning("의심 문장 발견: '%s...' -> 전체 문맥 분석으로 넘어갑니다.", sentence[:40])
            break

    if not needs_claude_check:
        logger.info("최종 판정: 정상. 1차 검사에서 의심되는 상황이 없습니다.")
        return {
            "stage1_detected": False,
            "stage1_sentence": "",
            "stage2_verdict": "NORMAL",
            "reason": "1차 검사에서 위험 문장이 발견되지 않았습니다.",
            "email_sent": False,
        }

    logger.info("2차 검사: Claude에게 파일 전체의 문맥 분석 요청")
    claude_result = claude_analyze(full_text)
    verdict = claude_result["verdict"]
    reason = claude_result["reason"]

    if verdict == "FALL":
        logger.error("최종 판정: 낙상. 전체 문맥상 낙상으로 확인되어 메일을 발송합니다.")
        logger.error("AI 판단 이유: %s", reason)
        email_sent = send_gmail_alert(
            verdict,
            reason,
            "전체 맥락 분석으로 감지됨",
            file_path=file_path,
            file_name=source_name,
        )
    else:
        logger.info("최종 판정: 정상/주의. 의심 문장이 있었으나 전체 흐름상 낙상이 아닙니다.")
        logger.info("AI 판단 이유: %s", reason)
        email_sent = False

    return {
        "stage1_detected": True,
        "stage1_sentence": detected_sentence,
        "stage2_verdict": verdict,
        "reason": reason,
        "email_sent": email_sent,
    }


def process_text_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        full_text = f.read()
    return process_text_content(
        full_text,
        source_name=os.path.basename(file_path),
        file_path=file_path,
    )


def main():
    if len(sys.argv) > 1:
        process_text_file(sys.argv[1])
        return 0

    logger.info("실시간 서버에서는 텍스트 내용을 직접 전달합니다.")
    logger.info("재처리가 필요하면 python fall_alert_checker.py <텍스트파일경로> 형태로 실행하세요.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
