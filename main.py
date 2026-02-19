from fastapi import FastAPI
from blockchain.query import fetch_events

app = FastAPI()


@app.get("/ping")
def read_root():
    fetch_events()
    return {"status": "ok"}
