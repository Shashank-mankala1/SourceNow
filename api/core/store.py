from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import uuid


@dataclass
class Ingest:
    ingest_id: str
    source_type: str # "text" (for now)
    text: str
    meta: dict = field(default_factory=dict)


@dataclass
class Job:
    job_id: str
    ingest_id: str
    stage: str = "queued" # queued|claims|done|error
    progress: int = 0
    message: Optional[str] = None
    results: Optional[dict] = None


class Store:
    def __init__(self) -> None:
        self.ingests: Dict[str, Ingest] = {}
        self.jobs: Dict[str, Job] = {}


    def new_ingest(self, text: str, source_type: str = "text", meta: Optional[dict] = None) -> str:
        iid = str(uuid.uuid4())
        self.ingests[iid] = Ingest(ingest_id=iid, source_type=source_type, text=text, meta=meta or {})
        return iid


    def new_job(self, ingest_id: str) -> str:
        jid = str(uuid.uuid4())
        self.jobs[jid] = Job(job_id=jid, ingest_id=ingest_id)
        return jid


STORE = Store()