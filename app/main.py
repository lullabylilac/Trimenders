from dotenv import load_dotenv
from core.logging_config import configure_logging


load_dotenv()
configure_logging()

from fastapi import FastAPI

from app.model_runtime import lifespan
from app.routes.dashboard import router as dashboard_router
from app.routes.video import router as video_router


app = FastAPI(lifespan=lifespan)
app.include_router(dashboard_router)
app.include_router(video_router)
