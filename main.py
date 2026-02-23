import asyncio

from fastapi import FastAPI
from blockchain.query import fetch_events
from blockchain.transact import validate_event

app = FastAPI()


@app.get("/ping")
def read_root():
    events = fetch_events()
    if len(events.events) != 0:
        for event in events.events:
            print(event)
            asyncio.run(validate_event(event.id, "yes", "my_course"))
    else:
        print("no events")

    return {"status": "ok"}
