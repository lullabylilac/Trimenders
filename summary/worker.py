import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from app.config import BASE_RESULT_DIR, LATEST_SUMMARY_INFO_FILE, SUMMARY_DIR
from core.files import TEXT_INDEX_PREFIX, write_json_atomic


load_dotenv()
logger = logging.getLogger(__name__)

CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("SUMMARY_CLAUDE_MODEL", "claude-sonnet-4-6")
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_RESULT_DIR, "texts"))
SUMMARY_INDEX_FILE = os.getenv(
    "SUMMARY_INDEX_FILE",
    os.path.join(SUMMARY_DIR, "_summary_index.jsonl"),
)

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)


def text_index_paths(start_time, end_time):
    current_date = start_time.date()
    end_date = end_time.date()
    while current_date <= end_date:
        yield os.path.join(LOG_DIR, f"{TEXT_INDEX_PREFIX}_{current_date:%Y-%m-%d}.jsonl")
        current_date += timedelta(days=1)


def parse_record_time(record):
    timestamp = record.get("timestamp")
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp)
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


def load_indexed_text_files(start_time, end_time):
    valid_files_with_time = []
    seen_paths = set()

    for index_path in text_index_paths(start_time, end_time):
        if not os.path.exists(index_path):
            continue

        with open(index_path, "r", encoding="utf-8") as index_file:
            for line in index_file:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                file_time = parse_record_time(record)
                file_path = record.get("path")
                if not file_time or not file_path:
                    continue
                if not (start_time <= file_time < end_time):
                    continue
                if file_path in seen_paths:
                    continue
                if not os.path.exists(file_path):
                    continue

                seen_paths.add(file_path)
                valid_files_with_time.append((file_path, file_time))

    return sorted(valid_files_with_time, key=lambda item: item[1])


def record_summary_file(summary_path, start_time, end_time, interval_min):
    file_path = Path(summary_path)
    record = {
        "name": file_path.name,
        "path": str(file_path),
        "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "interval_start": start_time.isoformat(timespec="seconds"),
        "interval_end": end_time.isoformat(timespec="seconds"),
        "interval_min": interval_min,
    }

    with open(SUMMARY_INDEX_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_json_atomic(LATEST_SUMMARY_INFO_FILE, record)


def build_flat_prompt(valid_files_with_time):
    contents = []
    for file_path, _file_time in valid_files_with_time:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                contents.append(f.read().strip())
        except Exception as exc:
            logger.warning("파일 읽기 실패 (%s): %s", os.path.basename(file_path), exc)
    return "\n".join(contents)


def build_chunked_timeline_prompt(valid_files_with_time, start_time, end_time, sub_chunk_min):
    current_sub_start = start_time
    combined_timeline_prompt = ""

    while current_sub_start < end_time:
        current_sub_end = current_sub_start + timedelta(minutes=sub_chunk_min)
        sub_start_str = current_sub_start.strftime("%H:%M")
        sub_end_str = current_sub_end.strftime("%H:%M")

        sub_chunk_contents = []
        for file_path, file_time in valid_files_with_time:
            if current_sub_start <= file_time < current_sub_end:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        sub_chunk_contents.append(f.read().strip())
                except Exception as exc:
                    logger.warning("파일 읽기 실패 (%s): %s", os.path.basename(file_path), exc)

        if sub_chunk_contents:
            combined_timeline_prompt += f"\n[구간 시각: {sub_start_str} ~ {sub_end_str}]\n"
            combined_timeline_prompt += "\n".join(sub_chunk_contents) + "\n"
            combined_timeline_prompt += "-" * 40 + "\n"

        current_sub_start = current_sub_end

    return combined_timeline_prompt


def summarize_interval(start_time, end_time, interval_min, sub_chunk_min=None):
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    valid_files_with_time = load_indexed_text_files(start_time, end_time)

    if not valid_files_with_time:
        logger.warning("인덱스에서 해당 구간의 분석 데이터를 찾지 못해 요약을 생략합니다.")
        return None

    if sub_chunk_min:
        combined_timeline_prompt = build_chunked_timeline_prompt(
            valid_files_with_time,
            start_time,
            end_time,
            sub_chunk_min,
        )
    else:
        combined_timeline_prompt = build_flat_prompt(valid_files_with_time)

    try:
        time_range_str = f"{start_time.strftime('%H:%M')} ~ {end_time.strftime('%H:%M')}"

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=(
                f"당신은 요양보호사입니다. 제공된 로그를 바탕으로 어르신의 행동 관찰 일지를 작성하세요.\n\n"
                "[작성 규칙]\n"
                f"1. 보고서의 첫 줄은 반드시 '{time_range_str} 행동 관찰 일지'라는 문구로 시작하세요.\n"
                "2. 별표(**)나 샵(#) 같은 마크다운 기호는 절대 사용하지 마세요. 오직 평문 텍스트로만 작성하세요.\n"
                "3. 표 형식이나 세부 타임라인 구분 없이, 전체적인 활동 내용을 하나의 자연스러운 글로 요약하세요.\n"
                "4. 요양보호사가 동료나 보호자에게 전달하듯 부드럽고 일상적인 한국어 문체를 사용하세요.\n"
                "5. 기계적이고 딱딱한 번역투를 버리고, 자연스럽고 간결한 일상 용어를 사용하세요.\n"
                "6. 주관적 추측은 배제하고, 눈에 보이는 핵심 행동만 자연스럽게 연결하세요.\n\n"
                "[출력 예시]\n"
                f"{time_range_str} 행동 관찰 일지\n\n"
                "관찰 시간 동안 어르신은 주방에서 설거지를 하셨습니다. 이후 거실로 이동하여 소파에 앉아 TV를 시청하셨고, "
                "도중에 잠시 일어나셔서 창문을 닫고 다시 자리에 앉으셨습니다."
            ),
            messages=[{"role": "user", "content": combined_timeline_prompt}],
        )
        summary_result = response.content[0].text
        save_timestamp = valid_files_with_time[-1][1].strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"summary_{save_timestamp}_{interval_min}min.txt"
        summary_path = os.path.join(SUMMARY_DIR, filename)

        with open(summary_path, "w", encoding="utf-8") as out_f:
            out_f.write(summary_result)

        record_summary_file(summary_path, start_time, end_time, interval_min)
        return filename

    except Exception as exc:
        logger.exception("요약 API 호출 실패: %s", exc)
        return None
