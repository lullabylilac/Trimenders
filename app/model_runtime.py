import os

os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from transformers import AutoProcessor
from vllm import LLM

from app.config import CHECKPOINT_PATH
from app.scheduler_runtime import start_summary_scheduler, stop_summary_scheduler


logger = logging.getLogger(__name__)
ml_models = {}
inference_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading processor from %s", CHECKPOINT_PATH)
    ml_models["processor"] = AutoProcessor.from_pretrained(
        CHECKPOINT_PATH,
        trust_remote_code=True,
    )

    logger.info("Loading vLLM engine from %s", CHECKPOINT_PATH)
    ml_models["llm"] = LLM(
        model=CHECKPOINT_PATH,
        trust_remote_code=True,
        gpu_memory_utilization=float(os.getenv("GPU_MEMORY_UTILIZATION", "0.8")),
        max_model_len=int(os.getenv("MAX_MODEL_LEN", "32768")),
        tensor_parallel_size=int(os.getenv("TENSOR_PARALLEL_SIZE", "1")),
        enforce_eager=os.getenv("ENFORCE_EAGER", "true").lower() == "true",
    )

    logger.info("Server is ready")
    start_summary_scheduler()
    try:
        yield
    finally:
        stop_summary_scheduler()
        ml_models.clear()
        logger.info("Model references cleared")
