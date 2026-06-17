from urllib.parse import urlencode

from app.config import (
    AGENT_DVR_BASE_URL,
    AGENT_DVR_IFRAME_URL,
    AGENT_DVR_OBJECT_ID,
    AGENT_DVR_STREAM_URL,
)


def build_agent_dvr_urls() -> dict[str, str]:
    stream_url = AGENT_DVR_STREAM_URL
    if not stream_url:
        query = urlencode(
            {
                "oid": AGENT_DVR_OBJECT_ID,
                "size": "1280x720",
                "maintainAR": "true",
            }
        )
        stream_url = f"{AGENT_DVR_BASE_URL}/video.mjpg?{query}"

    iframe_url = AGENT_DVR_IFRAME_URL
    if not iframe_url:
        query = urlencode(
            {
                "start": "Live",
                "ot": "2",
                "oid": AGENT_DVR_OBJECT_ID,
                "max": "true",
                "mini": "true",
            }
        )
        iframe_url = f"{AGENT_DVR_BASE_URL}/?{query}"

    return {
        "stream_url": stream_url,
        "iframe_url": iframe_url,
        "object_id": AGENT_DVR_OBJECT_ID,
    }
