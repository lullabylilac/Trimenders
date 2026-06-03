"""
낙상 감지 모듈 (임베딩 + Logistic Regression + Claude 2차 분석)
================================================================
텍스트 분석 결과 파일을 읽어서 문장 단위로 쪼갠 후 검사합니다.
1개라도 낙상이 발견되면 즉시 메일을 발송하고 해당 파일 검사를 종료합니다.
"""

'''
필요한 패키지 명령어 : pip install numpy sentence-transformers scikit-learn anthropic python-dotenv
'''

import sys
import io
import os
import re
import numpy as np
import pickle
import glob
import hashlib
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
import anthropic

# ===== [추가] 이메일 발송용 라이브러리 =====
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
import datetime
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

load_dotenv()

# ============================================================
# [설정]
# ============================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-6"  # (주의) claude-sonnet-4-6 대신 실제 존재하는 모델명으로 수정함
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
BASE_DIR = Path(__file__).resolve().parent

# 실제 텍스트 결과가 저장되는 경로 (utils.py와 동일하게 맞춤)
TEXT_DIR = "/workspace/development/generated_data/texts"

# ===== 이메일 설정 =====
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = "tjrdnjs0312@gmail.com"

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ============================================================
# [임베딩 모델 로딩]
# ============================================================
print("[초기화] 임베딩 모델 로딩 중...")
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
print(f"[초기화] 완료: {EMBEDDING_MODEL_NAME}")

# ============================================================
# [훈련 데이터] 낙상(1) vs 정상(0) (하드코딩 유지)
# ============================================================
TRAINING_DATA = [
    # ===== 낙상 / 위험 (1) =====
    ("The elderly person fell to the ground and is lying motionless.", 1),
    ("The person slipped on the wet floor and collapsed.", 1),
    ("They lost balance and tumbled down the stairs.", 1),
    ("The patient fell from the bed and is unable to get up.", 1),
    ("The person tripped over an obstacle and hit the ground hard.", 1),
    ("Found lying on the floor in an unnatural position, not moving.", 1),
    ("The elderly person went down suddenly and cannot stand.", 1),
    ("Collapsed near the bathroom door, appears unconscious.", 1),
    ("The person crumpled to the floor without warning.", 1),
    ("Detected a sudden drop in posture, person is now on the ground.", 1),
    ("The individual stumbled and crashed into the wall before falling.", 1),
    ("Person appears to have lost consciousness and is on the floor.", 1),
    ("The person is lying face down on the tile floor, no movement detected.", 1),
    ("Sudden fall detected, the person is struggling to get up.", 1),
    ("The elderly person toppled over while trying to stand from the chair.", 1),
    ("Person buckled at the knees and dropped to the floor.", 1),
    ("The resident was found sprawled on the hallway floor.", 1),
    ("The person has been on the ground for several minutes without moving.", 1),
    ("Appears to have fainted, body is limp on the floor.", 1),
    ("The person missed a step and rolled down the staircase.", 1),

    # ===== 주의 / 불안정 (1) =====
    ("The person is walking very unsteadily and grabbing the wall.", 1),
    ("Wobbling significantly while standing, looks about to fall.", 1),
    ("The elderly person is swaying and struggling to maintain balance.", 1),
    ("Legs appear weak, the person is having difficulty walking.", 1),
    ("The person is leaning heavily on furniture for support.", 1),
    ("Noticed unsteady gait, the person nearly fell twice.", 1),
    ("Head dropped forward in the chair, not responding to sounds.", 1),
    ("No movement detected for over 20 minutes, person appears unresponsive.", 1),
    ("The person has not changed position in a very long time.", 1),
    ("Sitting motionless with eyes closed, no reaction to surroundings.", 1),

    # ===== 정상 (0) =====
    ("The person is sitting comfortably on the sofa watching television.", 0),
    ("Eating a meal at the dining table with normal posture.", 0),
    ("Walking steadily through the hallway at a normal pace.", 0),
    ("The elderly person is sleeping peacefully in bed.", 0),
    ("Doing light stretching exercises in the living room.", 0),
    ("Reading a book while seated in an armchair.", 0),
    ("Standing in the kitchen preparing a cup of tea.", 0),
    ("The person is talking on the phone while sitting.", 0),
    ("Lying in bed under covers, regular breathing visible.", 0),
    ("Calmly resting on the recliner with eyes closed, appears to be napping.", 0),
    ("The person got up from the chair and walked to the kitchen.", 0),
    ("Watering plants on the balcony, moving normally.", 0),
    ("Folding laundry on the bed, coordinated movements.", 0),
    ("Sitting at the desk writing something.", 0),
    ("Watching TV and occasionally changing channels with the remote.", 0),
    ("The person stood up slowly from the sofa and stretched.", 0),
    ("Drinking water while standing by the counter.", 0),
    ("Petting the cat while seated on the couch.", 0),
    ("Cleaning the table with a cloth, normal activity.", 0),
    ("The elderly person is having a conversation with a visitor.", 0),

    # ===== 헷갈리기 쉬운 정상 (0) =====
    ("The person slowly laid down on the sofa to rest.", 0),
    ("Carefully sat down on the floor to do yoga stretches.", 0),
    ("Bent down to pick up something from the floor, then stood back up.", 0),
    ("Lowered themselves onto the bed for an afternoon nap.", 0),
    ("Kneeled down to tie their shoelaces.", 0),
    ("Got down on the floor to play with a pet.", 0),
    ("Leaned against the wall briefly to adjust their slipper.", 0),
    ("Sat down on the floor cushion to meditate.", 0),
    ("The person grabbed a cane to avoid falling and continued walking safely.", 0),
    ("Almost lost balance but caught the railing and recovered.", 0),

    # ===== 부정문 하드네거티브 (정상, 0) ===== ← 추가
    ("There is no indication of loss of balance; the person is walking steadily.", 0),
    ("No signs of falling were observed; the person remains stable.", 0),
    ("The person did not lose balance and continued moving normally.", 0),
    ("There is no sign of a fall; the elderly person is sitting upright.", 0),
    ("No loss of balance detected, posture appears normal and controlled.", 0),
    ("Nothing in the scene suggests the person slipped or collapsed.", 0),
    ("There is no evidence of the person falling or losing balance.", 0),
    ("The person shows no signs of instability; movement is smooth and controlled.", 0),
]

def _training_hash():
    raw = "".join(t[0] for t in TRAINING_DATA).encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:8]

CLASSIFIER_PATH = BASE_DIR / f"fall_classifier_{_training_hash()}.pkl"


# ============================================================
# [분류기 학습 / 로드]
# ============================================================
def train_classifier():
    print(f"\n[훈련] 데이터 {len(TRAINING_DATA)}건 임베딩 중...")
    texts = [t[0] for t in TRAINING_DATA]
    labels = np.array([t[1] for t in TRAINING_DATA])

    embeddings = embedding_model.encode(texts, show_progress_bar=False)
    clf = LogisticRegression(max_iter=1000, random_state=42)
    clf.fit(embeddings, labels)

    with open(CLASSIFIER_PATH, "wb") as f:
        pickle.dump(clf, f)
    return clf


def load_or_train_classifier():
    if Path(CLASSIFIER_PATH).exists():
        with open(CLASSIFIER_PATH, "rb") as f:
            return pickle.load(f)
    return train_classifier()


classifier = load_or_train_classifier()



# ============================================================
# [분석 함수들]
# ============================================================
def embedding_classify(sentence: str) -> dict:
    embedding = embedding_model.encode([sentence])
    probabilities = classifier.predict_proba(embedding)[0]
    alert_prob = probabilities[1]
    THRESHOLD = 0.65
    return {
        "detected": alert_prob >= THRESHOLD,
        "confidence": alert_prob,
        "label": "ALERT" if alert_prob >= 0.5 else "NORMAL",
    }


CLAUDE_SYSTEM_PROMPT = """You are a safety expert analyzing a sequence of CCTV observations for elderly care monitoring.
Analyze the FULL CONTEXT of the provided log and classify the final situation.

IMPORTANT — distinguish a PERSON falling from a CAMERA disturbance:
- A person fall: a specific PERSON changes posture (collapses, slips, drops to the floor) while the rest of the scene/background stays stable.
- A camera issue (NOT a fall): the ENTIRE scene suddenly tilts, rotates, inverts, shakes, goes blurry/dark, or the viewpoint changes abruptly. This means the camera was bumped, moved, or fell — not the person. Classify as NORMAL.
- NEGATION: phrases like "no indication of loss of balance", "no signs of falling", "did not fall", "remained stable" describe a SAFE situation, NOT a fall.

Classify the final situation as one of:
1. FALL - The PERSON ultimately fell, collapsed, slipped, or lost consciousness.
2. CAUTION - The person was unstable, wobbling, or almost fell, but recovered or has not fallen.
3. NORMAL - Voluntary actions, resting, sleeping, normal activities, OR an apparent camera/viewpoint disturbance.

Respond ONLY in this format:
VERDICT: FALL or CAUTION or NORMAL
REASON: (one line explanation based on the full context)
"""


def claude_analyze(full_text: str) -> dict:
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=CLAUDE_SYSTEM_PROMPT,
            # 한 문장이 아닌 파일의 '전체 텍스트'를 Claude에게 던집니다.
            messages=[{"role": "user", "content": f"[CCTV Full Sequence Log]\n{full_text}"}],
        )
        result = response.content[0].text.strip()
        verdict, reason = "UNKNOWN", result

        for line in result.split("\n"):
            line_upper = line.upper()
            if "VERDICT" in line_upper:
                if "FALL" in line_upper and "CAUTION" not in line_upper:
                    verdict = "FALL"
                elif "CAUTION" in line_upper:
                    verdict = "CAUTION"
                elif "NORMAL" in line_upper:
                    verdict = "NORMAL"
            if "REASON" in line_upper:
                reason = line.split(":", 1)[-1].strip()

        return {"verdict": verdict, "reason": reason}
    except Exception as e:
        return {"verdict": "ERROR", "reason": f"Claude error: {e}"}


# ============================================================
# [메일 발송 함수]
# ============================================================
def send_gmail_alert(verdict, reason, target_sentence, file_path):
    try:
        KST = datetime.timezone(datetime.timedelta(hours=9))
        now_time = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        filename = os.path.basename(file_path)
        subject = f"🚨 [CareNote] 긴급 낙상 감지: ({now_time})"

        body = f"""
        시스템에서 낙상 사고가 감지되었습니다. 원본 영상을 확인 바랍니다.

        [감지 시간]: {now_time}
        [분석 파일명]: {filename}"

        [AI 판정]: {verdict}
        [상세 이유]: {reason}

        * 상세 내용은 첨부된 텍스트 파일을 통해서도 확인하실 수 있습니다.
        
        - 어르신의 하루를 읽다, CareNote 팀 드림.
        """

        msg = MIMEMultipart()
        msg['From'] = formataddr(('CareNote', SENDER_EMAIL))
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # 파일 첨부
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                attachment = MIMEApplication(f.read(), _subtype="txt")
                attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(attachment)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"  📧 [알림] Gmail 알람 발송 완료! (파일: {filename})")
    except Exception as e:
        print(f"  ❌ [에러] 메일 발송 실패: {e}")


# ============================================================
# [핵심] 텍스트 파일 읽기 및 분석 파이프라인
# ============================================================
# ============================================================
# [핵심] 텍스트 파일 읽기 및 분석 파이프라인 (문맥 기반으로 변경)
# ============================================================
def process_text_file(file_path: str):
    print(f"\n{'=' * 60}")
    print(f"📂 파일 분석 시작: {os.path.basename(file_path)}")
    print(f"{'=' * 60}")

    with open(file_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    sentences = re.split(r'[\n\.]+', full_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

    # 1. 1차 빠른 스캔 (문장 중 하나라도 위험 정황이 있는지 필터링)
    needs_claude_check = False
    print("  [1차 검사] 문장 단위 위험 정황 스캔 중...")

    for sentence in sentences:
        emb = embedding_classify(sentence)
        if emb["detected"]:
            needs_claude_check = True
            print(f"    ↳ ⚠️ 의심 문장 발견: '{sentence[:40]}...' -> 전체 문맥 분석으로 넘어갑니다.")
            break  # 의심 문장이 하나라도 나오면 더 스캔할 필요 없이 바로 전체 분석으로 넘어감

    # 2. 2차 정밀 분석 (Claude가 파일 전체 텍스트를 읽고 맥락 판단)
    if needs_claude_check:
        print("  [2차 검사] Claude에게 파일 전체의 문맥 분석을 요청합니다...")
        claude_result = claude_analyze(full_text)

        if claude_result['verdict'] == "FALL":
            print(f"\n  🚨 [최종 판정: 낙상] 전체 문맥상 낙상으로 확인되었습니다! 메일을 발송합니다.")
            print(f"  - AI 판단 이유: {claude_result['reason']}")

            # 메일 발송 시 타겟 문장 대신 '전체 맥락 분석'이라는 점을 명시합니다.
            send_gmail_alert(claude_result['verdict'], claude_result['reason'], "전체 맥락 분석으로 감지됨", file_path)

        else:
            print(f"  ✅ [최종 판정: 정상/주의] 의심 문장이 있었으나, 전체 흐름상 낙상이 아닙니다.")
            print(f"  - AI 판단 이유: {claude_result['reason']}")

    else:
        print("  ✅ [최종 판정: 정상] 1차 검사에서 의심되는 상황이 전혀 없습니다.")


# ============================================================
# [실행 메인 블록] 디렉토리 내 모든 txt 파일 스캔
# ============================================================
if __name__ == "__main__":
    print("\n🔍 텍스트 분석 디렉토리를 스캔합니다...")

    if not os.path.exists(TEXT_DIR):
        print(f"❌ 경로를 찾을 수 없습니다: {TEXT_DIR}")
        sys.exit()

    # TEXT_DIR 안의 모든 .txt 파일 가져오기
    txt_files = glob.glob(os.path.join(TEXT_DIR, "*.txt"))

    if not txt_files:
        print("⚠️ 분석할 텍스트 파일이 없습니다.")
    else:
        print(f"📄 총 {len(txt_files)}개의 파일을 발견했습니다. 검사를 시작합니다.\n")
        for txt_file in txt_files:
            process_text_file(txt_file)

        print("\n🎉 모든 파일 검사가 완료되었습니다!")