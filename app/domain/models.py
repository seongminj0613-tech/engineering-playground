from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class EvidenceItem(BaseModel):
    title: str
    source: str | None = None
    url: str | None = None
    quote: str | None = None
    score_hint: float | None = None

class ScoreBreakdown(BaseModel):
    feasibility: float = 0
    impact: float = 0
    risk: float = 0
    novelty: float = 0
    total_score: float = 0

class IdeaCard(BaseModel):
    id: str
    title: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    scores: ScoreBreakdown = Field(default_factory=ScoreBreakdown)

    # optional fields
    rank: int | None = None
    rank_delta: int | None = None
    trend: str | None = None

    @classmethod
    def from_any(cls, obj: dict[str, Any]) -> "IdeaCard":
        # 너 기존 키 구조가 달라도 흡수 가능하게 최소 안전장치
        if "id" not in obj:
            obj["id"] = obj.get("key") or obj.get("uuid") or obj.get("title", "unknown")
        if "scores" not in obj:
            obj["scores"] = obj.get("score", {}) or {}
        return cls.model_validate(obj)