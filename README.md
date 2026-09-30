# CareNote

CareNote는 AgentDVR에서 녹화된 영상을 RunPod 서버로 보내고, 서버에서 영상을 분석한 뒤 낙상 여부를 판단하고 요약보고서를 생성하는 프로젝트입니다.

README에서는 다음 내용을 확인하실 수 있습니다.

- 어떤 파일을 실행해야 하는지
- AgentDVR, RunPod, 요약 스케줄러가 각각 어떤 역할인지
- 영상 분석 결과가 어디에 저장되는지
- 폴더 탐색 때문에 느려지던 문제를 어떻게 해결했는지
- 테스트와 문제 해결은 어떤 순서로 하면 되는지

[설명 웹사이트](https://trimenders.vercel.app/)

[설명 유튜브 링크](https://youtu.be/CMo3d6dvhyM?si=uIL7f3HANLKJgZvD)

## 한 줄 요약

로컬 PC의 AgentDVR가 영상을 녹화하면 `send_video.py`가 RunPod 서버의 `server.py`로 영상을 보내고, 서버는 Qwen 모델로 영상 설명 텍스트를 만든 뒤 낙상 감지, 이메일 알림, 요약보고서 생성을 처리합니다.

## 전체 동작 흐름

```text
AgentDVR 녹화 완료
-> send_video.py 실행
-> RunPod 서버 /health 확인
-> RunPod 서버 /analyze-video/로 영상 업로드
-> 서버가 영상을 임시 저장
-> Qwen3-VL 모델이 영상 내용을 텍스트로 분석
-> 분석 텍스트 파일 저장
-> 같은 텍스트를 바로 낙상 감지 함수로 전달
-> 1차 낙상 감지
-> 필요하면 Claude 2차 판단
-> 낙상으로 판단되면 이메일 알림
-> 정해진 주기마다 요약보고서 생성 및 이메일 발송
```

중요한 점은 낙상 감지에서 폴더를 다시 뒤져서 최신 파일을 찾지 않는다는 것입니다. 서버가 방금 만든 분석 텍스트를 바로 함수에 넘기기 때문에 실시간 감지 지연이 줄어듭니다.

## 실행 위치

이 프로젝트는 크게 두 위치에서 동작합니다.

| 위치 | 실행 파일 | 역할 |
| --- | --- | --- |
| RunPod 서버 | `server.py` | 영상을 받고, 모델 분석, 낙상 감지, 요약 스케줄러를 실행 |
| 로컬 Windows PC | `send_video.py` | AgentDVR가 만든 녹화 영상을 RunPod 서버로 전송 |

RunPod에서는 서버를 실행하고, 로컬 PC에서는 AgentDVR 이벤트에 `send_video.py`를 연결합니다.

## 폴더 구조

```text
carenote_modular/
  server.py                 RunPod에서 실행하는 서버 진입점
  send_video.py             AgentDVR 영상 전송 진입점
  trigger.example.bat       AgentDVR 연결용 Windows 배치파일 예시
  .env.example              GitHub에 올리는 환경 변수 예시 파일
  .gitignore                개인 설정/로그/캐시 제외 규칙
  main_scheduler.py         3분 주기 요약 스케줄러
  chunked_scheduler.py      60분 주기 요약 스케줄러
  summary_worker.py         요약 생성 함수 호환용 진입점
  fall_alert_checker.py     저장된 텍스트 파일 낙상 재검사용 진입점
  carenote_dashboard.py     기존 코드 호환용 대시보드 진입점
  utils.py                  기존 코드 호환용 유틸 진입점

  app/                      FastAPI 서버, 모델 로딩, 영상 분석 작업
  client/                   RunPod로 영상을 보내는 클라이언트 코드
  core/                     파일 저장, 인덱스, 공통 로깅 설정
  dashboard/                대시보드 상태와 설정 저장
  detection/                낙상 감지, Claude 2차 판단, 낙상 이메일
    training_data.py        1차 낙상 감지 재학습용 문장 데이터
    train_classifier.py     fall_classifier.pkl 재학습 스크립트
  summary/                  요약 생성, 요약 이메일, 요약 스케줄러
  web/                      대시보드 HTML
  models/                   낙상 1차 감지 모델 파일
```

## 주요 파일 설명

| 파일 | 설명 |
| --- | --- |
| `server.py` | 서버 실행 파일입니다. 내부적으로 `app.main:app`을 불러옵니다. |
| `send_video.py` | AgentDVR가 녹화 완료 후 실행할 파일입니다. 내부적으로 `client.send_video`를 실행합니다. |
| `trigger.example.bat` | AgentDVR와 `send_video.py`를 연결할 때 참고하는 Windows 배치파일 예시입니다. |
| `.env.example` | GitHub에 올려도 되는 환경 변수 예시입니다. 실제 비밀값은 `.env`에 넣습니다. |
| `.gitignore` | `.env`, 로그, 캐시, 임시 파일이 GitHub에 올라가지 않도록 막습니다. |
| `main_scheduler.py` | 3분마다 요약보고서를 생성하는 스케줄러입니다. |
| `chunked_scheduler.py` | 60분마다 요약보고서를 생성합니다. 내부적으로 10분 단위 조각을 만들어 긴 시간대를 안정적으로 요약합니다. |
| `summary_worker.py` | 요약 생성 함수를 직접 import해서 쓰던 기존 코드와 호환되도록 남겨둔 파일입니다. |
| `fall_alert_checker.py` | 이미 저장된 텍스트 파일 하나를 다시 낙상 검사할 때 사용합니다. |
| `models/fall_classifier.pkl` | 1차 낙상 감지에 쓰는 분류 모델입니다. |
| `detection/training_data.py` | `fall_classifier.pkl`을 다시 학습할 때 쓰는 문장 데이터입니다. |
| `detection/train_classifier.py` | `training_data.py`를 이용해 `fall_classifier.pkl`을 새로 만드는 스크립트입니다. |
| `web/dashboard.html` | 브라우저에서 보는 대시보드 화면입니다. |

## 실행 전 준비물

RunPod 서버 쪽에는 다음이 준비되어 있어야 합니다.

- Python 실행 환경
- Qwen3-VL 모델 파일
- GPU 사용 가능한 RunPod Pod
- 필요한 Python 라이브러리
- Anthropic API 키
- 이메일 발송 계정 정보

로컬 Windows PC 쪽에는 다음이 필요합니다.

- AgentDVR
- Python 실행 환경
- `send_video.py`가 있는 프로젝트 폴더
- RunPod 서버 주소

## 필요한 Python 라이브러리

환경에 따라 이미 설치되어 있을 수 있습니다. 없다면 다음 계열의 라이브러리가 필요합니다.

```text
fastapi
uvicorn
python-dotenv
requests
anthropic
numpy
scikit-learn
pytz
pydantic
sentence-transformers
transformers
vllm
qwen-vl-utils
```

RunPod의 GPU, CUDA, vLLM, Transformers 버전은 사용하는 이미지와 모델에 따라 맞춰야 합니다.

## 환경 변수 설정

환경 변수는 `.env` 파일에 넣거나 RunPod 환경 변수로 설정할 수 있습니다.

GitHub에는 실제 `.env`를 올리지 말고 `.env.example`만 올립니다. 처음 실행하는 사람은 `.env.example`을 복사해서 자기 환경에 맞는 `.env`를 만들면 됩니다.

가장 중요한 값:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
SENDER_EMAIL=sender@example.com
SENDER_PASSWORD=your_email_app_password
JANG_EMAIL=receiver@example.com
CARENOTE_SERVER_URL=https://your-runpod-id-9000.proxy.runpod.net
```

모델과 저장 위치:

```env
CHECKPOINT_PATH=/workspace/models/qwen3-vl-8b-instruct-fp8
BASE_RESULT_DIR=/workspace/development/generated_data
```

서버 모델 옵션:

```env
GPU_MEMORY_UTILIZATION=0.8
MAX_MODEL_LEN=32768
TENSOR_PARALLEL_SIZE=1
ENFORCE_EAGER=true
MODEL_TIMEOUT_SEC=60
MAX_UPLOAD_BYTES=1073741824
```

요약 스케줄러:

```env
ENABLE_SUMMARY_SCHEDULER=true
```

낙상 감지:

```env
EMAIL_ALERT_ENABLED=true
FALL_CLASSIFIER_THRESHOLD=0.65
FALL_CLASSIFIER_PATH=models/fall_classifier.pkl
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
CLAUDE_MODEL=claude-sonnet-4-6
```

로그:

```env
LOG_LEVEL=INFO
CARENOTE_LOG_FILE=/workspace/development/generated_data/logs/carenote.log
CARENOTE_CLIENT_LOG_FILE=logs/send_video.log
```

AgentDVR 대시보드 표시용:

```env
AGENT_DVR_BASE_URL=http://localhost:8090
AGENT_DVR_OBJECT_ID=1
AGENT_DVR_STREAM_URL=
AGENT_DVR_IFRAME_URL=
```

`AGENT_DVR_OBJECT_ID`는 AgentDVR에서 카메라/장치마다 부여되는 ID입니다. 현재 카메라 ID가 `1`이면 위처럼 `1`로 둡니다.

## 가장 기본 실행 방법

RunPod에서 프로젝트 폴더로 이동한 뒤 서버를 실행합니다.

```bash
uvicorn server:app --host 0.0.0.0 --port 9000
```

가상환경을 먼저 활성화하고 AgentDVR 화면 표시 설정까지 같이 넣는다면 다음처럼 실행합니다. 가상환경 경로는 사용하는 RunPod 이미지에 맞게 바꿉니다.

```bash
source /path/to/your/venv/bin/activate

export AGENT_DVR_BASE_URL="http://localhost:8090/"
export AGENT_DVR_OBJECT_ID="1"

uvicorn server:app --host 0.0.0.0 --port 9000
```

코드에서는 `AGENT_DVR_BASE_URL` 뒤의 `/`를 자동으로 정리하므로 `http://localhost:8090/`와 `http://localhost:8090` 둘 다 사용할 수 있습니다.

대시보드의 AgentDVR 영상 주소는 서버가 만든 뒤 브라우저에 전달합니다. 그래서 `localhost:8090`은 대시보드를 열고 있는 PC에서 AgentDVR에 접근 가능한 주소여야 합니다.

정상적으로 켜졌는지 확인합니다.

```bash
curl http://127.0.0.1:9000/health
```

정상 응답 예시:

```json
{
  "status": "ok",
  "model_loaded": true
}
```

외부 PC에서는 RunPod 프록시 주소로 확인합니다.

```text
https://your-runpod-id-9000.proxy.runpod.net/health
```

대시보드는 다음 주소에서 확인합니다.

```text
https://your-runpod-id-9000.proxy.runpod.net/dashboard
```


## 3분마다 요약보고서를 만들고 싶을 때

3분 주기 요약은 `main_scheduler.py`가 담당합니다.

서버에 붙어 있는 기본 60분 요약과 중복되지 않게 하려면 먼저 자동 요약을 끕니다.

`.env`:

```env
ENABLE_SUMMARY_SCHEDULER=false
```

터미널 1에서 서버 실행:

```bash
uvicorn server:app --host 0.0.0.0 --port 9000
```

터미널 2에서 3분 요약 스케줄러 실행:

```bash
python main_scheduler.py
```

이렇게 하면 영상 분석 서버는 계속 켜져 있고, 요약보고서는 3분마다 별도 프로세스에서 생성됩니다.

## 60분 요약을 따로 실행하고 싶을 때

서버와 분리해서 60분 요약 스케줄러만 실행하려면 다음 명령을 사용합니다.

```bash
python chunked_scheduler.py
```

이 경우에도 서버 자동 요약이 켜져 있으면 중복 실행될 수 있으므로, 분리 운영할 때는 `ENABLE_SUMMARY_SCHEDULER=false`를 권장합니다.

## AgentDVR에서 영상 보내는 방법

AgentDVR는 녹화가 끝났을 때 특정 스크립트를 실행할 수 있습니다.

이 프로젝트에서는 로컬 Windows PC의 `send_video.py`를 AgentDVR 이벤트에 연결합니다.

GitHub에는 개인 PC 경로가 들어간 실제 배치파일 대신 `trigger.example.bat`를 올립니다. 실제 PC에서는 이 파일을 복사해서 AgentDVR가 실행하는 `trigger.bat`로 사용하면 됩니다.

배치파일에서 사용할 수 있는 환경 변수:

```text
CARENOTE_PYTHON_EXE=C:\path\to\python.exe
CARENOTE_SEND_VIDEO_SCRIPT=C:\path\to\carenote_modular\send_video.py
CARENOTE_TRIGGER_LOG_FILE=C:\path\to\logs\trigger.log
```

이 값을 따로 설정하지 않으면 `trigger.example.bat`는 기본적으로 `python` 명령과 배치파일이 있는 폴더의 `send_video.py`를 사용합니다.

AgentDVR가 영상 파일 경로를 인자로 넘기면 `send_video.py`는 다음 순서로 동작합니다.

1. 전달받은 영상 파일이 실제로 있는지 확인합니다.
2. 파일 크기가 안정될 때까지 잠시 기다립니다.
3. RunPod 서버의 `/health`를 확인합니다.
4. 서버와 모델이 준비되어 있으면 `/analyze-video/`로 업로드합니다.
5. 서버가 접수하면 로컬 영상 파일을 삭제합니다.

로컬 영상을 삭제하지 않으려면 다음 값을 설정합니다.

```env
DELETE_LOCAL_VIDEO_AFTER_SEND=false
```

수동 테스트:

```bash
python send_video.py C:\path\to\test.mp4
```

## 서버 API

| 주소 | 방식 | 설명 |
| --- | --- | --- |
| `/health` | GET | 서버와 모델 준비 상태 확인 |
| `/analyze-video/` | POST | 영상 업로드 및 분석 요청 |
| `/dashboard` | GET | 대시보드 화면 |
| `/api/dashboard/status` | GET | 대시보드 상태 JSON |
| `/api/dashboard/settings` | GET | 수신 이메일 설정 확인 |
| `/api/dashboard/settings` | POST | 수신 이메일 설정 변경 |
| `/api/dashboard/settings/reset` | POST | 수신 이메일 설정 초기화 |

영상 업로드는 바로 분석 결과를 기다리지 않고 `202 Accepted`로 접수됩니다.

응답 예시:

```json
{
  "status": "queued",
  "id": "test_abcdef12",
  "message": "영상 업로드 완료. 분석은 백그라운드에서 진행합니다."
}
```

분석은 서버 백그라운드에서 진행되며, 결과는 텍스트 파일과 대시보드 상태로 확인합니다.

## 데이터 저장 위치

기본 저장 루트:

```text
/workspace/development/generated_data
```

하위 폴더:

```text
generated_data/
  videos/       업로드된 영상 임시 저장
  texts/        Qwen 분석 텍스트 저장
  summaries/    요약보고서 저장
  status/       대시보드 상태와 설정 저장
  logs/         설정한 경우 로그 파일 저장
```

텍스트 저장 예시:

```text
texts/
  camera_2026-06-17_10-00-00.txt
  _text_index_2026-06-17.jsonl
  _latest_text.json
```

요약 저장 예시:

```text
summaries/
  summary_2026-06-17_10-00-00_to_2026-06-17_11-00-00.txt
  _summary_index.jsonl
  _latest_summary.json
```

## 폴더가 안 열리고 느려지던 문제 해결

이전 방식의 핵심 문제는 텍스트 파일이 많아질수록 최신 파일을 찾기 위해 폴더 전체를 탐색해야 한다는 점이었습니다.

파일 수가 적을 때는 문제가 잘 보이지 않지만, 장기간 운영하면 `texts` 폴더 안의 파일이 계속 늘어납니다. 그러면 최신 파일 하나를 찾기 위해 많은 파일 이름과 수정 시간을 확인해야 하고, 저장소가 느린 환경에서는 대시보드나 낙상 감지가 지연될 수 있습니다.

현재 구조는 두 가지로 나눠 해결합니다.

첫 번째, 실시간 낙상 감지는 파일 탐색을 하지 않습니다.

서버는 Qwen 분석이 끝나면 분석 텍스트를 파일로 저장합니다. 동시에 그 텍스트 문자열을 낙상 감지 함수에 바로 넘깁니다. 즉, 낙상 감지는 "방금 저장한 파일을 다시 폴더에서 찾는 방식"이 아니라 "방금 생성된 텍스트를 바로 검사하는 방식"입니다.

두 번째, 장기 보관과 요약 처리는 인덱스를 사용합니다.

분석 텍스트 파일은 그대로 저장합니다. 대신 새 텍스트가 저장될 때마다 아래 인덱스 파일을 같이 갱신합니다.

```text
_text_index_YYYY-MM-DD.jsonl
_latest_text.json
```

요약보고서도 마찬가지로 최신 요약 파일 정보를 별도 파일에 기록합니다.

```text
_summary_index.jsonl
_latest_summary.json
```

그래서 대시보드나 요약 로직은 매번 폴더 전체를 훑지 않고, 필요한 인덱스만 읽습니다.

정리하면 다음과 같습니다.

| 목적 | 이전 방식 | 현재 방식 |
| --- | --- | --- |
| 실시간 낙상 감지 | 저장된 파일을 다시 찾아 읽음 | 생성된 텍스트를 바로 함수에 전달 |
| 최신 텍스트 표시 | 폴더 전체 탐색 | `_latest_text.json` 읽기 |
| 요약 대상 찾기 | 폴더 전체 탐색 | 날짜별 인덱스 파일 읽기 |
| 장기 보관 | 텍스트 파일 저장 | 텍스트 파일 저장 유지 |

## 낙상 감지 흐름

낙상 감지는 2단계로 구성되어 있습니다.

1차 감지:

- `models/fall_classifier.pkl` 모델 사용
- Qwen이 생성한 텍스트를 임베딩으로 변환
- 낙상 가능성이 기준값 이상이면 의심 상황으로 판단

2차 판단:

- 1차 감지에서 의심되면 Claude가 텍스트를 다시 읽고 판단
- 실제 낙상으로 판단되면 이메일 알림 발송

낙상인데 정상으로 처리되는 경우에는 먼저 기준값을 낮춰 테스트합니다.

```env
FALL_CLASSIFIER_THRESHOLD=0.45
```

값을 낮추면 낙상을 더 잘 잡을 수 있지만, 정상 상황을 낙상으로 오판할 가능성도 늘어납니다. 장기적으로는 실제 Qwen 출력 문장을 모아서 `fall_classifier.pkl`을 다시 학습하는 것이 가장 좋습니다.

## 1차 낙상 감지 모델 재학습

`models/fall_classifier.pkl`은 1차 낙상 감지에 사용하는 학습 완료 모델입니다.

주의할 점은 `.pkl` 안에 원본 문장 데이터가 그대로 들어 있는 것이 아니라는 점입니다. 원본 문장들은 `detection/training_data.py`에 보관하고, `.pkl`에는 그 문장들로 학습된 Logistic Regression 모델의 가중치가 저장됩니다.

정확도를 올리고 싶을 때는 다음 순서로 작업합니다.

1. `detection/training_data.py`에 실제 Qwen 출력 문장을 추가합니다.
2. 낙상/주의 상황이면 라벨을 `1`로 둡니다.
3. 정상 상황이면 라벨을 `0`으로 둡니다.
4. 재학습 명령을 실행합니다.
5. 새로 생성된 `models/fall_classifier.pkl`로 서버를 다시 실행합니다.

재학습 명령:

```bash
python -m detection.train_classifier
```

기본 동작:

- 기존 `models/fall_classifier.pkl`이 있으면 `.bak` 백업 파일을 먼저 만듭니다.
- `detection/training_data.py`의 `TRAINING_DATA`를 임베딩합니다.
- Logistic Regression 모델을 다시 학습합니다.
- 새 모델을 `models/fall_classifier.pkl`에 저장합니다.

백업 없이 바로 덮어쓰고 싶을 때:

```bash
python -m detection.train_classifier --no-backup
```

다른 위치에 저장하고 싶을 때:

```bash
python -m detection.train_classifier --output /workspace/development/generated_data/models/fall_classifier.pkl
```

학습만 테스트하고 파일은 저장하지 않으려면:

```bash
python -m detection.train_classifier --dry-run
```

재학습 후 서버에서 새 모델을 쓰게 하려면 서버를 재시작하는 것이 가장 확실합니다.

## 이메일 종류

이메일은 두 종류가 있습니다.

| 위치 | 역할 |
| --- | --- |
| `detection/emailer.py` | 낙상 발생 시 긴급 알림 이메일 발송 |
| `summary/emailer.py` | 정기 요약보고서 이메일 발송 |

두 파일 모두 발신 계정은 `SENDER_EMAIL`, `SENDER_PASSWORD`를 사용합니다.

수신자는 기본적으로 `JANG_EMAIL`을 사용하며, 대시보드에서 수신 이메일을 바꾸면 낙상 알림은 대시보드 설정을 우선 사용합니다.

## 로그

서버와 스케줄러는 Python `logging`을 사용합니다.

기본 로그 레벨:

```env
LOG_LEVEL=INFO
```

더 자세히 보고 싶을 때:

```env
LOG_LEVEL=DEBUG
```

파일에도 저장하고 싶을 때:

```env
CARENOTE_LOG_FILE=/workspace/development/generated_data/logs/carenote.log
```

로컬 PC에서 `send_video.py`가 남기는 전송 로그는 별도 파일을 사용합니다.

```env
CARENOTE_CLIENT_LOG_FILE=logs/send_video.log
```

## 처음 테스트하는 추천 순서

### 1. RunPod 서버 실행

```bash
uvicorn server:app --host 0.0.0.0 --port 9000
```

### 2. 서버 상태 확인

```bash
curl http://127.0.0.1:9000/health
```

`model_loaded`가 `true`가 될 때까지 기다립니다.

### 3. 외부 주소 확인

로컬 PC 브라우저에서 아래 주소를 엽니다.

```text
https://your-runpod-id-9000.proxy.runpod.net/health
```

### 4. 대시보드 확인

```text
https://your-runpod-id-9000.proxy.runpod.net/dashboard
```

### 5. 짧은 영상 직접 업로드

RunPod 또는 로컬 PC에서 테스트 영상을 하나 보냅니다.

```bash
curl -X POST -F "file=@test.mp4" https://your-runpod-id-9000.proxy.runpod.net/analyze-video/
```

### 6. 분석 텍스트 확인

```bash
ls /workspace/development/generated_data/texts
```

아래 파일이 생겼는지 확인합니다.

```text
분석결과.txt
_text_index_YYYY-MM-DD.jsonl
_latest_text.json
```

### 7. 요약보고서 확인

60분 요약은 시간이 지나야 생성됩니다. 바로 테스트하고 싶다면 3분 스케줄러를 따로 실행합니다.

```bash
python main_scheduler.py
```

요약 파일 확인:

```bash
ls /workspace/development/generated_data/summaries
```

### 8. AgentDVR 연결

직접 업로드 테스트가 성공한 뒤 AgentDVR 이벤트에 `send_video.py`를 연결합니다.

## 자주 생기는 문제와 확인 방법

### `/health`가 502를 반환함

502는 대부분 RunPod 프록시가 서버 앱에 연결하지 못한다는 뜻입니다.

확인할 것:

- Pod가 Running 상태인지
- 서버를 `--host 0.0.0.0 --port 9000`으로 실행했는지
- RunPod 프록시 주소의 포트가 9000인지
- 서버가 실행 중에 에러로 종료되지 않았는지
- 모델 로딩 중 메모리 부족이 발생하지 않았는지

### `/health`는 되지만 `model_loaded=false`

FastAPI 서버는 켜졌지만 Qwen 모델이 아직 준비되지 않은 상태입니다.

확인할 것:

- 모델 경로 `CHECKPOINT_PATH`가 맞는지
- RunPod GPU 메모리가 충분한지
- `GPU_MEMORY_UTILIZATION`, `MAX_MODEL_LEN` 값을 너무 크게 잡지 않았는지
- 서버 로그에 모델 로딩 오류가 없는지

### 영상 업로드가 `503 Model is not ready`를 반환함

모델 로딩이 끝나기 전에 영상을 보낸 상태입니다.

`/health`에서 `model_loaded=true`가 나온 뒤 다시 테스트합니다.

### 영상 업로드가 `dropped`로 나옴

서버가 이미 다른 영상을 분석 중이라는 뜻입니다.

현재 구조는 한 번에 하나의 영상만 분석하도록 잠금이 걸려 있습니다. 이전 영상 분석이 끝난 뒤 다음 영상을 처리합니다.

### 요약보고서가 생성되지 않음

요약 대상 시간 구간에 분석 텍스트가 없으면 요약보고서를 만들지 않습니다.

확인할 것:

- `/workspace/development/generated_data/texts`에 분석 텍스트가 있는지
- `_text_index_YYYY-MM-DD.jsonl` 파일이 있는지
- `ANTHROPIC_API_KEY`가 설정되어 있는지
- 스케줄러가 실제로 실행 중인지

### 이메일이 오지 않음

확인할 것:

- `SENDER_EMAIL`이 맞는지
- `SENDER_PASSWORD`가 일반 비밀번호가 아니라 앱 비밀번호인지
- `JANG_EMAIL` 또는 대시보드 수신 이메일이 맞는지
- Gmail 보안 설정에서 SMTP 로그인이 허용되는지

### AgentDVR 전송 로그에 서버 준비 안 됨이 반복됨

`send_video.py`는 영상을 보내기 전에 `/health`를 확인합니다.

다음 중 하나일 가능성이 큽니다.

- RunPod 서버가 아직 켜지지 않음
- 서버는 켜졌지만 모델 로딩이 끝나지 않음
- RunPod 프록시 주소가 틀림
- 포트가 9000이 아님
- 서버가 중간에 에러로 종료됨

먼저 브라우저에서 아래 주소를 직접 열어 확인합니다.

```text
https://your-runpod-id-9000.proxy.runpod.net/health
```

## 빠른 명령 모음

서버 실행:

```bash
uvicorn server:app --host 0.0.0.0 --port 9000
```

서버 상태 확인:

```bash
curl http://127.0.0.1:9000/health
```

테스트 영상 업로드:

```bash
curl -X POST -F "file=@test.mp4" http://127.0.0.1:9000/analyze-video/
```

3분 요약 스케줄러:

```bash
python main_scheduler.py
```

60분 요약 스케줄러:

```bash
python chunked_scheduler.py
```

텍스트 파일 낙상 재검사:

```bash
python fall_alert_checker.py /workspace/development/generated_data/texts/example.txt
```

AgentDVR 전송 수동 테스트:

```bash
python send_video.py C:\path\to\test.mp4
```

1차 낙상 감지 모델 재학습:

```bash
python -m detection.train_classifier
```

## 핵심 내용

- RunPod에서 기본으로 실행할 것은 `server.py`입니다.
- 로컬 AgentDVR에서 실행할 것은 `send_video.py`입니다.
- 서버를 켜면 기본적으로 60분 요약 스케줄러도 같이 실행됩니다.
- 3분 요약을 쓰려면 `main_scheduler.py`를 따로 실행합니다.
- 실시간 낙상 감지는 텍스트 내용을 바로 전달받기 때문에 폴더 전체 탐색 지연을 피합니다.
- 텍스트와 요약 파일은 장기 보관을 위해 계속 저장됩니다.
- 대시보드와 요약 로직은 최신 정보 파일과 인덱스를 사용합니다.
- 1차 낙상 감지 정확도를 개선하려면 `detection/training_data.py`를 수정하고 `python -m detection.train_classifier`로 `.pkl`을 다시 만듭니다.
