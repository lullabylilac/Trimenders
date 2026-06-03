import os
import re
import anthropic
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

# 설정
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL="claude-sonnet-4-6"
SUMMARY_DIR = "./summaries"
client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# Anthropic 클라이언트 객체는 상단에 이미 선언되어 있다고 가정합니다.
# from anthropic import Anthropic
# client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# 기존 하드코딩된 /root/ 경로를 지우고 아래 코드로 교체합니다.
BASE_RESULT_DIR = os.getenv("BASE_RESULT_DIR", "/workspace/development/generated_data")
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_RESULT_DIR, "texts"))
SUMMARY_DIR = os.getenv("SUMMARY_DIR", os.path.join(BASE_RESULT_DIR, "summaries"))


def summarize_interval(start_time, end_time, interval_min, sub_chunk_min):
    """start_time부터 end_time까지(interval_min)의 데이터를 스케줄러가 넘겨준 sub_chunk_min 단위로
    쪼개서 텍스트를 모은 뒤, 하나의 완성된 관찰 일지로 요약합니다.
    """
    if not os.path.exists(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)

    # 1. 60분 전체 구간 내에 존재하는 파일들 먼저 정교하게 필터링
    try:
        all_files = sorted([f for f in os.listdir(LOG_DIR) if f.endswith(".txt")])
    except FileNotFoundError:
        print(f"Error: LOG_DIR '{LOG_DIR}'를 찾을 수 없습니다.")
        return None

    valid_files_with_time = []
    last_file_timestamp = ""
    time_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")

    for f in all_files:
        match = time_pattern.search(f)
        if match:
            dt_str = match.group(1)
            try:
                file_time = datetime.strptime(dt_str, "%Y-%m-%d_%H-%M-%S")

                # 전체 1시간(interval_min) 바운더리 내에 들어오는지 1차 필터링
                if start_time <= file_time < end_time:
                    valid_files_with_time.append((f, file_time))
                    last_file_timestamp = dt_str  # 원본 파일명 규칙용 매핑
                elif file_time >= end_time:
                    break
            except ValueError:
                continue

    # 구간 내에 수집된 원본 데이터가 단 하나도 없으면 요약 생략
    if not valid_files_with_time:
        return None

    # 2. 1시간 구간을 sub_chunk_min(예: 10분)씩 쪼개며 원본 로그 바인딩
    current_sub_start = start_time
    combined_timeline_prompt = ""

    while current_sub_start < end_time:
        current_sub_end = current_sub_start + timedelta(minutes=sub_chunk_min)

        sub_start_str = current_sub_start.strftime("%H:%M")
        sub_end_str = current_sub_end.strftime("%H:%M")

        sub_chunk_contents = []
        for filename, file_time in valid_files_with_time:
            if current_sub_start <= file_time < current_sub_end:
                file_path = os.path.join(LOG_DIR, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        sub_chunk_contents.append(f.read().strip())
                except Exception as e:
                    print(f"파일 읽기 실패 ({filename}): {e}")

        # 10분 구간 데이터가 있을 때만 명시하여 Claude에게 맥락 제공
        if sub_chunk_contents:
            combined_timeline_prompt += f"\n[구간 시각: {sub_start_str} ~ {sub_end_str}]\n"
            combined_timeline_prompt += "\n".join(sub_chunk_contents) + "\n"
            combined_timeline_prompt += "-" * 40 + "\n"

        current_sub_start = current_sub_end

    # ============================================================
    # 🚀 Claude API 호출 (원본 규칙 철저 유지)
    # ============================================================
    try:
        # 시간대 문자열 생성 (예: 21:25 ~ 21:28)
        time_range_str = (
            f"{start_time.strftime('%H:%M')} ~ {end_time.strftime('%H:%M')}"
        )

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=(
                f"당신은 요양보호사입니다. 제공된 로그를 바탕으로 어르신의 행동 관찰 일지를 작성하세요.\n\n"
                "[작성 규칙]\n"
                f"1. 보고서의 첫 줄은 반드시 '{time_range_str} 행동 관찰 일지'라는 문구로 시작하세요.\n"
                "2. 별표(**)나 샵(#) 같은 마크다운 기호는 절대 사용하지 마세요. 오직 평문 텍스트로만 작성하세요.\n"
                "3. 표 형식이나 세부 타임라인 구분 없이, 전체적인 활동 내용을 하나의 자연스러운 글로 요약하세요.\n"
                "4. 요양보호사가 동료나 보호자에게 전달하듯 부드럽고 일상적인 한국어 문체(~하셨습니다, ~하셨음)를 사용하세요. \n"
                "5. 기계적이고 딱딱한 번역투(예: '의류 투입 조작', '정지 상태 유지')를 버리고, "
                "요양보호사가 쓰는 자연스럽고 간결한 일상 용어(예: '세탁기 사용', '설거지', '넘어지심', '누워 계심')를 사용하세요.\n"
                "6. '정지 상태 유지' 같은 딱딱한 표현 대신 '가만히 앉아 계셨음', '계속 누워 계셨음' 등 직관적인 표현을 쓰세요.\n"
                "7. 주관적 추측은 배제하고, 눈에 보이는 핵심 행동만 자연스럽게 연결하여 하나의 보고서로 완성하세요.\n\n"
                "[출력 예시]\n"
                f"{time_range_str} 행동 관찰 일지\n\n"
                "관찰 시간 동안 어르신은 주방에서 설거지를 하셨습니다. 이후 거실로 이동하여 소파에 앉아 TV를 시청하셨고, "
                "도중에 잠시 일어나셔서 창문을 닫고 다시 자리에 앉으셨습니다."
            ),
            messages=[{"role": "user", "content": combined_timeline_prompt}],
        )
        summary_result = response.content[0].text

        # 파일명 규칙 적용
        save_timestamp = (
            last_file_timestamp
            if last_file_timestamp
            else end_time.strftime("%Y-%m-%d_%H-%M-%S")
        )
        filename = f"summary_{save_timestamp}_{interval_min}min.txt"

        with open(
            os.path.join(SUMMARY_DIR, filename), "w", encoding="utf-8"
        ) as out_f:
            out_f.write(summary_result)

        return filename

    except Exception as e:
        print(f"API Error: {e}")
        return None