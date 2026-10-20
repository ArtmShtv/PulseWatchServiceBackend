import uvicorn
import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import auth_routes
from app.api.routes.monitor import monitor_router
from app.core.config import settings
from app.ws.router import router as ws_router
from app.ws.manager import manager
from app.ws.subscriber import redis_listener


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(redis_listener(manager))
    yield
    task.cancel()
    await task


app = FastAPI(lifespan=lifespan)

app.include_router(auth_routes)
app.include_router(monitor_router)
app.include_router(ws_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "PulseWatch Backend root url"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        reload = True
    )