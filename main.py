import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from llm.decision import cron_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cron_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)


@app.get("/ping")
def read_root():
    return {"status": "ok"}
