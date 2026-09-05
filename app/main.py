from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import router, vm


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    try:
        vm._cleanup_orphaned_temps(max_age_seconds=0)
    except Exception:
        pass


app = FastAPI(title="Video Downloader Web", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)