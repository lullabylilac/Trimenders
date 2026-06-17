from qwen_vl_utils import process_vision_info
from vllm import SamplingParams


def run_qwen_analysis(video_path: str, processor, llm) -> str:
    system_prompt = """
    You are an objective video analysis AI. Your output must ONLY consist of the [Activity Log] section.

    [Strict Constraints]
    1. Factual Description Only: Describe physical movements, velocity, and balance. If the center of gravity shifts faster than a controlled sitting motion, specify it as a 'loss of balance' or 'sudden collapse'.
    2. No Summary/Status: Do not provide "Current Status", "Summary of Concerns", or "Movement Quality" sections.
    3. Describe the direction of the fall based on which body part makes contact with the floor first. Do not assume the direction unless the movement trajectory is clearly visible.
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
