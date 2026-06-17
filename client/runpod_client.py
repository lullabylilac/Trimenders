import os

import requests

from client.config import ANALYZE_URL, HEALTH_URL, REQUEST_TIMEOUT
from client.logging_utils import write_log


def check_server_ready():
    try:
        response = requests.get(HEALTH_URL, timeout=(5, 30))
        if response.status_code != 200:
            write_log(f"서버 상태 확인 실패: 상태 코드 {response.status_code}")
            return False

        data = response.json()
        if not data.get("model_loaded"):
            write_log("서버는 켜져 있지만 AI 모델이 아직 준비되지 않았습니다.")
            return False

        return True
    except requests.exceptions.RequestException as exc:
        write_log(f"서버 상태 확인 실패: {exc}")
        return False


def upload_video(video_filepath):
    with open(video_filepath, "rb") as video_file:
        files = {
            "file": (
                os.path.basename(video_filepath),
                video_file,
                "video/mp4",
            )
        }
        return requests.post(
            ANALYZE_URL,
            files=files,
            timeout=REQUEST_TIMEOUT,
        )
