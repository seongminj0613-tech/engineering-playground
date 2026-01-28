from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ScoreBreakdown(BaseModel):
    feasibility: float = 0.0
    evidence: float = 0.0
    momentum: float = 0.0
    novelty: float = 0.0
    priority: float = 0.0
    confidence: float = 0.0

class EvidenceItem(BaseModel):
    title: str
    source: str = ""
    published_at: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    relevance: float = 0.0

class IdeaCard(BaseModel):
    idea_id: str
    title: str
    summary: str

    tags: List[str] = Field(default_factory=list)
    cluster_id: Optional[str] = None

    scores: ScoreBreakdown = Field(default_factory=ScoreBreakdown)

    drivers: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)

    evidence: List[EvidenceItem] = Field(default_factory=list)
    trend: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())