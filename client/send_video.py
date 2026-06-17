import os
import sys

import requests

from client.config import DELETE_LOCAL_VIDEO_AFTER_SEND
from client.file_stability import wait_until_file_stable
from client.logging_utils import write_log
from client.runpod_client import check_server_ready, upload_video


SUCCESS_STATUS_CODES = {200, 202}


def handle_success_response(response, video_filepath):
    result_data = response.json()
    request_id = result_data.get("id", "unknown")
    status = result_data.get("status", "success")
    description = result_data.get("description")
    video_deleted = result_data.get("video_deleted")

    write_log(f"서버 접수 완료: status={status}, id={request_id}, server_video_deleted={video_deleted}")
    if description:
        write_log(f"분석 내용: {description}")

    if DELETE_LOCAL_VIDEO_AFTER_SEND:
        os.remove(video_filepath)
        write_log("처리 완료: 로컬 임시 영상 파일을 삭제했습니다.")
    else:
        write_log("처리 완료: 로컬 영상 파일은 보존했습니다.")

    write_log("-" * 50)
    return 0


def main():
    if len(sys.argv) < 2:
        write_log("오류: 전달받은 영상 파일 경로가 없습니다.")
        return 1

    video_filepath = sys.argv[1]

    if not os.path.exists(video_filepath):
        write_log(f"오류: 파일을 찾을 수 없습니다 -> {video_filepath}")
        return 1

    if not wait_until_file_stable(video_filepath):
        write_log(f"오류: 영상 파일 저장이 완료되지 않았거나 파일 크기가 안정되지 않았습니다 -> {video_filepath}")
        return 1

    if not check_server_ready():
        write_log("처리 중단: RunPod 서버가 준비되지 않았습니다.")
        return 1

    write_log(f"전송 시작: {os.path.basename(video_filepath)} 파일을 서버로 보냅니다.")

    try:
        response = upload_video(video_filepath)

        if response.status_code in SUCCESS_STATUS_CODES:
            return handle_success_response(response, video_filepath)

        write_log(f"전송 실패: 서버 오류 상태 코드 {response.status_code}")
        write_log(f"서버 응답 내용: {response.text}")
        return 1
    except requests.exceptions.Timeout:
        write_log("타임아웃: RunPod 서버 응답이 너무 오래 걸렸습니다.")
    except requests.exceptions.ConnectionError:
        write_log("네트워크 오류: RunPod 서버에 접속할 수 없습니다. Pod가 켜져 있는지 확인하세요.")
    except requests.exceptions.RequestException as exc:
        write_log(f"요청 오류 발생: {exc}")
    except Exception as exc:
        write_log(f"치명적 오류 발생: {exc}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
