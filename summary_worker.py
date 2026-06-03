import os
import re
import anthropic
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# 설정
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL="claude-sonnet-4-6"
LOG_DIR = "/workspace/development/generated_data/texts"
# LOG_DIR = "/workspace/members/jang/analysis_results/texts/Abnormal_Behavior_Falldown_inside"
# LOG_DIR = "/workspace/members/jang/analysis_results/texts/daily-dementia"
SUMMARY_DIR = "/workspace/development/generated_data/summaries"
client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

def summarize_interval(start_range, end_range, interval_min):
    """
    특정 시간 범위(start_range ~ end_range) 내의 로그를 요약하여 저장합니다.
    """
    if not os.path.exists(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)

    # target_files = []
    # all_files = sorted([f for f in os.listdir(LOG_DIR) if f.endswith('.txt')])
    # last_file_timestamp = ""
    
    # # 날짜와 시간 형식을 찾는 정규표현식 패턴 (예: 2026-05-12_21-20-02)
    # time_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")

    # for f in all_files:
    #     match = time_pattern.search(f)
    #     if match:
    #         dt_str = match.group(1) # 찾은 날짜/시간 텍스트 추출
    #         try:
    #             # parts = f.split('_')
    #             # dt_str = f"{parts[1]}_{parts[2]}"
    #             file_time = datetime.strptime(dt_str, "%Y-%m-%d_%H-%M-%S")
    
    #             # 지정된 시간 구간 안에 포함되는지 확인
    #             if start_range <= file_time < end_range:
    #                 # target_files.append(f)
    #                 target_files.append((f, dt_str)) # 파일명과 추출한 시간 텍스트를 함께 저장
    #                 last_file_timestamp = dt_str
    #         except ValueError:
    #             continue

    # if not target_files:
    #     return None

    # 1. 파일 목록 필터링 최적화
    # 전체 파일을 정규식으로 검사하기 전, 확장자와 기본 정렬을 먼저 수행합니다.
    try:
        all_files = sorted([f for f in os.listdir(LOG_DIR) if f.endswith('.txt')])
    except FileNotFoundError:
        print(f"Error: LOG_DIR '{LOG_DIR}'를 찾을 수 없습니다.")
        return None

    target_files = []
    last_file_timestamp = ""
    time_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")

    for f in all_files:
        match = time_pattern.search(f)
        if match:
            dt_str = match.group(1)
            try:
                file_time = datetime.strptime(dt_str, "%Y-%m-%d_%H-%M-%S")
                
                # 지정된 시간 구간 안에 포함되는지 확인
                if start_range <= file_time < end_range:
                    target_files.append((f, dt_str))
                    last_file_timestamp = dt_str
                # 정렬된 상태이므로, 이미 범위를 넘어선 파일이 나오면 루프를 종료하여 속도를 높임
                elif file_time >= end_range:
                    break
            except ValueError:
                continue

    if not target_files:
        return None


    # 텍스트 병합
    combined_logs = ""
    for f, dt_str in target_files:
        with open(os.path.join(LOG_DIR, f), 'r', encoding='utf-8') as file:
            # dt_str (예: 2026-05-12_21-20-02) 에서 시간 부분만 잘라서 [21:20:02] 형태로 만듦
            time_part = dt_str.split('_')[1].replace('-', ':')
            combined_logs += f"[{time_part}] {file.read()}\n"

    # Claude API 호출
    try:
        # 시간대 문자열 생성 (예: 21:25 ~ 21:28)
        time_range_str = f"{start_range.strftime('%H:%M')} ~ {end_range.strftime('%H:%M')}"
        
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
            messages=[{"role": "user", "content": combined_logs}]
        )
        summary_result = response.content[0].text

    # # Claude API 호출
    # try:
    #     response = client.messages.create(
    #         model="claude-sonnet-4-6", # 또는 현재 작동하는 모델 이름
    #         max_tokens=4096,           # [수정] 출력이 끊기지 않도록 토큰 한도 대폭 증가
    #         system=(
    #             f"당신은 요양보호사입니다. 제공된 {interval_min}분 동안의 카메라 관찰 로그를 바탕으로 "
    #             "어르신의 행동 관찰 일지를 작성해야 합니다.\n\n"
    #             "[작성 지침]\n"
    #             "1. 표 형식이나 분/초 단위의 세세한 타임라인 구분은 절대 사용하지 마세요. "
    #             f"오직 '{interval_min}분 동안의 전반적인 활동 요약'이라는 단일 문단 또는 짧은 글 형태로 작성하세요.\n"
    #             "2. 기계적이고 딱딱한 번역투(예: '의류 투입 조작', '정지 상태 유지')를 버리고, "
    # #             "요양보호사가 쓰는 자연스럽고 간결한 일상 용어(예: '세탁기 사용', '설거지', '넘어지심', '누워 계심')를 사용하세요.\n"
    #             "3. 별도의 [경고], [낙상 감지] 같은 특수 섹션을 만들지 마세요. 있는 사실만 부드럽게 서술하세요.\n"
    #             "4. 주관적 추측은 배제하고, 눈에 보이는 핵심 행동만 자연스럽게 연결하여 하나의 보고서로 완성하세요.\n\n"
    #             "[출력 예시]\n"
    #             "관찰 시간 동안 어르신은 주방에 들어오셔서 신발을 정리하고 싱크대 주변을 정리하셨습니다. "
    #             "손을 씻고 설거지를 하시던 중 중심을 잃고 뒤로 넘어지셨습니다. "
    #             "이후 세탁실로 이동하여 세탁기를 사용하시다 문틀을 잡고 앉는 과정에서 다시 한번 넘어지시는 모습이 관찰되었습니다."
    #         ),
    #         messages=[{"role": "user", "content": combined_logs}]
    #     )
    #     summary_result = response.content[0].text
    
    # # Claude API 호출
    # try:
    #     response = client.messages.create(
    #         model=CLAUDE_MODEL,
    #         max_tokens=1024,
    #         system=(
    #             f"당신은 홈 케어 시스템의 활동 분석 전문가입니다. "
    #             f"제공된 {interval_min}분 동안의 로그를 바탕으로 핵심 행동을 요약하세요.\n"
    #             "1. 주관적인 추측은 배제하고 객관적인 행동(예: 설거지, TV 시청, 넘어짐 등) 위주로 작성하세요.\n"
    #             "2. 반드시 한국어로 번역하여 출력하세요.\n"
    #             "3. 동일한 동작이 반복되면 하나로 통합하여 흐름을 설명하세요."
    #         ),
    #         messages=[{"role": "user", "content": combined_logs}]
    #     )
    #     summary_result = response.content[0].text
        
        # 파일명 규칙 적용
        save_timestamp = last_file_timestamp if last_file_timestamp else end_range.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"summary_{save_timestamp}_{interval_min}min.txt"
        
        with open(os.path.join(SUMMARY_DIR, filename), 'w', encoding='utf-8') as out_f:
            out_f.write(summary_result)
        
        return filename
    except Exception as e:
        print(f"API Error: {e}")
        return None