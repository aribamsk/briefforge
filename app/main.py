"""BriefForge HTTP API."""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.graph import build_graph

app = FastAPI(
    title="BriefForge",
    description="A planner, researcher, writer, and editor that produce a cited brief.",
    version="1.0.0",
)


class BriefRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    audience: str = Field(default="general professional audience", max_length=200)
    notes: str = Field(default="", max_length=20000)


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "pipeline": "plan -> research -> write -> critique"}


@app.post("/brief")
def create_brief(request: BriefRequest) -> dict:
    try:
        result = get_graph().invoke(
            {
                "topic": request.topic,
                "audience": request.audience,
                "notes": request.notes,
            }
        )
    except Exception as error:
        raise HTTPException(
            status_code=502, detail=f"Brief generation failed: {error}"
        ) from error

    return {
        "topic": request.topic,
        "questions": result.get("questions", []),
        "revisions": result.get("revision", 0),
        "critique": result.get("critique", ""),
        "brief": result.get("final", ""),
    }
