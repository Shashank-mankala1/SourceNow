from pydantic import BaseModel, Field
from typing import List, Optional


class IngestRequest(BaseModel):
    text: str = Field(..., description="Plain text to analyze")
    source_type: str = Field("text", description="text for this milestone")
    meta: Optional[dict] = None


class IngestResponse(BaseModel):
    ingest_id: str


class AnalyzeRequest(BaseModel):
    ingest_id: str
    mode: str = Field("fast", description="fast|quality (placeholder)")


class Timestamp(BaseModel):
    start: float
    end: float


# class Citation(BaseModel):
#     title: str
#     publisher: str
#     url: str
#     published_at: Optional[str] = None
#     tier: Optional[str] = None

# add a metadata bucket if your Citation model doesn't have one yet
class Citation(BaseModel):
    title: str
    url: str
    publisher: str
    tier: str  # "A" Fact-check | "B" Wikipedia | "C" Fallback
    metadata: Optional[dict] = None


class ClaimResult(BaseModel):
    id: str
    claim: str
    verdict: str
    confidence: float
    timestamps: List[Timestamp] = []
    citations: List[Citation] = []
    why: str


class ResultsResponse(BaseModel):
    source: dict
    claims: List[ClaimResult]


class StatusResponse(BaseModel):
    stage: str
    progress: int
    message: Optional[str] = None