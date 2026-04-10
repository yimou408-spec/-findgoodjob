from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field(..., description="岗位名称")
    company: str = Field(..., description="公司名称")
    source: str | None = Field(default=None, description="岗位来源")
    jd_text: str = Field(..., min_length=20, description="完整岗位 JD 文本")


class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    source: str | None
    jd_text: str
    analysis_result: str | None

    model_config = {"from_attributes": True}


class AnalyzeJobResponse(BaseModel):
    job_id: int = Field(..., description="岗位 ID")
    analysis_result: str = Field(..., description="岗位 JD 分析结果")


class ResumeRevisionRequest(BaseModel):
    resume_text: str = Field(..., min_length=20, description="原始简历文本")


class ResumeRevisionResponse(BaseModel):
    job_id: int = Field(..., description="岗位 ID")
    revised_resume: str = Field(..., description="结合目标岗位生成的简历修订结果")
