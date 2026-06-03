import os
import shutil
from pathlib import Path

from fastapi import UploadFile
from qwen_vl_utils import process_vision_info
from vllm import SamplingParams


BASE_RESULT_DIR = os.getenv("BASE_RESULT_DIR", "/workspace/development/generated_data")
TEXT_DIR = os.path.join(BASE_RESULT_DIR, "texts")
VIDEO_DIR = os.path.join(BASE_RESULT_DIR, "videos")

for directory in (TEXT_DIR, VIDEO_DIR):
    os.makedirs(directory, exist_ok=True)


def save_uploaded_video(file: UploadFile, filename: str) -> str:
    """Save an uploaded video under VIDEO_DIR."""
    safe_filename = Path(filename).name
    video_path = os.path.join(VIDEO_DIR, safe_filename)

    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return video_path


def save_analysis_text(text: str, filename: str) -> str:
    """Save the analysis result as a UTF-8 text file under TEXT_DIR."""
    safe_stem = Path(filename).stem
    text_path = os.path.join(TEXT_DIR, f"{safe_stem}.txt")

    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)

    return text_path


def run_qwen_analysis(video_path: str, processor, llm) -> str:
    """Analyze a video with Qwen VL through vLLM."""
    system_prompt = """
    You are an objective video analysis AI. Your output must ONLY consist of the [Activity Log] section.

    [Strict Constraints]
    1. Factual Description Only: Describe physical movements, velocity, and balance. If the center of gravity shifts faster than a controlled sitting motion, specify it as a 'loss of balance' or 'sudden collapse'.
    2. No Summary/Status: Do not provide "Current Status", "Summary of Concerns", or "Movement Quality" sections.
    3. Describe the direction of the fall based on which body part makes contact with the floor first (e.g., knees, chest, side, or back). Do not assume the direction unless the movement trajectory is clearly visible.
    4. No Inference: Describe the fall as an "uncontrolled rapid descent" if it lacks bracing motions, but do not guess the medical cause.
    5. Output Format: Strictly follow the format below without any additional text.
    """

    user_prompt = """
    Analyze the provided video clip.
    Provide a factual description of the movements.

    ### [Activity Log]
    - Observation:
    """

    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {
            "role": "user",
            "content": [
                {"type": "video", "video": video_path, "fps": 5.0},
                {"type": "text", "text": user_prompt.strip()},
            ],
        },
    ]

    text = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    _, video_inputs, video_kwargs = process_vision_info(
        messages,
        return_video_kwargs=True,
        return_video_metadata=True,
    )

    inputs = [
        {
            "prompt": text,
            "multi_modal_data": {"video": video_inputs},
            "mm_processor_kwargs": video_kwargs,
        }
    ]
    sampling_params = SamplingParams(
        temperature=0.2,
        max_tokens=256,
        repetition_penalty=1.2,
    )
    outputs = llm.generate(inputs, sampling_params=sampling_params)

    if not outputs or not outputs[0].outputs:
        raise RuntimeError("Model returned no output.")

    return outputs[0].outputs[0].text.strip()