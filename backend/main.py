"""
FastAPI backend for the USJ -> Wijerama tuk-pooling app.

Run locally with:
    uvicorn main:app --reload --port 8000
Then open http://localhost:8000 in a browser (frontend + API are served
from the same app, so there's no CORS setup to worry about).

API endpoints (all under /api):
    POST /api/request            body: {"name": "..."}  -> joins the live queue
    GET  /api/status/{student_id} -> current status (waiting or matched)
    GET  /api/admin/queue         -> live dashboard snapshot (queue + recent dispatches)
    POST /api/admin/simulate      -> adds a fake student instantly (demo/testing helper)
"""

import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from queue_manager import QueueManager

app = FastAPI(title="USJ to Wijerama Tuk Pooling")

manager = QueueManager()


@app.on_event("startup")
async def start_background_dispatcher():
    async def loop():
        while True:
            await asyncio.sleep(15)  # check the queue every 15 seconds
            manager.tick()

    asyncio.create_task(loop())


class RequestBody(BaseModel):
    name: str = ""


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "Tuk pooling service running"}


@app.post("/api/request")
def request_ride(body: RequestBody):
    entry = manager.add_student(body.name)
    return {"id": entry["id"], "name": entry["name"]}


@app.get("/api/status/{student_id}")
def status(student_id: str):
    return manager.get_status(student_id)


@app.get("/api/admin/queue")
def admin_queue():
    return manager.admin_snapshot()


# Serve the frontend last, so it doesn't shadow the /api routes above.
app.mount("/", StaticFiles(directory="static", html=True), name="static")