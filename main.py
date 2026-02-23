import asyncio

from fastapi import FastAPI
from blockchain.query import fetch_events
from blockchain.transact import validate_event

app = FastAPI()


@app.get("/ping")
def read_root():
    return {"status": "ok"}
