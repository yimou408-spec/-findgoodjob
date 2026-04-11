from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field(..., description="岗位名称")
    company: str = Field(..., description="公司名称")
    jd_text: str = Field(..., min_length=20, description="完整岗位 JD 文本")


class JobUpdate(BaseModel):
    title: str = Field(..., description="岗位名称")
    company: str = Field(..., description="公司名称")
    jd_text: str = Field(..., min_length=20, description="完整岗位 JD 文本")


class JobResponse(BaseModel):
    id: int
    title: str
    company: str
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
    revised_resume: str = Field(..., description="修订后的简历文本")
    match_score: int | None = Field(default=None, description="简历与岗位的匹配度评分")
    match_explanation: str | None = Field(default=None, description="匹配度评分说明")


class ResumeDocumentParseResponse(BaseModel):
    filename: str = Field(..., description="上传文件名")
    content_type: str = Field(..., description="文件 MIME 类型")
    extracted_text: str = Field(..., description="从文件中提取出的文本")


class ResumeRevisionRecordResponse(BaseModel):
    id: int
    job_id: int
    source_resume_text: str
    revised_resume: str
    match_score: int | None
    match_explanation: str | None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class AssistantMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sequence: int
    created_at: str | None = None

    model_config = {"from_attributes": True}


class AssistantThreadResponse(BaseModel):
    thread_id: int
    job_id: int
    can_chat: bool
    summary_text: str | None
    workspace_summary: str
    messages: list[AssistantMessageResponse]
    latest_resume_revision: ResumeRevisionRecordResponse | None = None


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户在助手页输入的问题")


class AssistantChatResponse(BaseModel):
    thread_id: int
    job_id: int
    message: AssistantMessageResponse
    summary_text: str | None
    workspace_summary: str
