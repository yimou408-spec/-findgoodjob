from pydantic import BaseModel, Field


class ResumeRewriteRequest(BaseModel):
    jd_id: int
    resume_content: str = Field(..., min_length=20)


class ResumeRewriteResponse(BaseModel):
    revision_id: int
    jd_id: int
    revised_content: str
    rationale: str
