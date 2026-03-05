import os
import time

import asyncpg

# TODO: TEST


async def fetch_events():
    url = os.environ.get("DATABASE_URL")
    conn = await asyncpg.connect(url)
    ACTIVE_EVENT = "ACTIVE"
    time_now = int(round(time.time() * 1000))

    rows = await conn.fetch("""
    SELECT *
    FROM event
    WHERE end_time < $1
    AND status = $2
    """,
                            time_now,
                            ACTIVE_EVENT)

    await conn.close()
    return rows
