from pydantic import BaseModel
from typing import List, Dict, Optional

class ClassifyRequest(BaseModel):
    texts: List[str]
    platform: Optional[str] = None

class OneResult(BaseModel):
    label: str
    score: float
    scores: Dict[str, float]
    raw: dict | None = None
    reasons: dict | None = None

class ClassifyResponse(BaseModel):
    results: List[OneResult]