from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    jd_id: int


class AnalyzeResponse(BaseModel):
    jd_id: int
    summary: str
    required_skills: list[str]
    risks: list[str]
