from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Any
from agent import BusinessResearchGraph

app = FastAPI()
assistant = BusinessResearchGraph()


class ProcessPayload(BaseModel):
    query: str
    state: Optional[dict] = None


@app.post("/process")
async def process(payload: ProcessPayload):
    result = assistant.process_query(payload.query, payload.state)
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}
