from fastapi import FastAPI

import uvicorn

from app.api.routes.auth import auth_routes
from app.api.routes.monitor import monitor_router

app = FastAPI()

app.include_router(auth_routes)
app.include_router(monitor_router)


@app.get("/")
def root():
    return {"message": "PulseWatch Backend"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        reload = True
    )