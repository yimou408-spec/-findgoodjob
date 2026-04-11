from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field(..., description="岗位名称")
    company: str = Field(..., description="公司名称")
    source: str | None = Field(default=None, description="岗位来源")
    jd_text: str = Field(..., min_length=20, description="完整岗位 JD 文本")


class JobUpdate(BaseModel):
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
    analysis_improvement_advice: str | None

    model_config = {"from_attributes": True}


class AnalyzeJobResponse(BaseModel):
    job_id: int = Field(..., description="岗位 ID")
    analysis_result: str = Field(..., description="岗位 JD 分析结果")
    analysis_improvement_advice: str | None = Field(default=None, description="岗位改进建议")


class ResumeRevisionRequest(BaseModel):
    resume_text: str = Field(..., min_length=20, description="原始简历文本")


class ResumeRevisionResponse(BaseModel):
    job_id: int = Field(..., description="岗位 ID")
    revised_resume: str = Field(..., description="结合目标岗位生成的简历修订结果")
    match_score: int | None = Field(default=None, description="修订后简历与岗位的匹配度评分")
    match_explanation: str | None = Field(default=None, description="匹配度评分说明")


class ResumeDocumentParseResponse(BaseModel):
    filename: str = Field(..., description="上传文件名")
    content_type: str = Field(..., description="文件 MIME 类型")
    extracted_text: str = Field(..., description="从文件中提取出的文本")
