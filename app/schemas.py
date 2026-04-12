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
    retrieval_note: str | None = None
    source_links: list[str] = []

    model_config = {"from_attributes": True}


class AssistantThreadResponse(BaseModel):
    thread_id: int
    job_id: int
    can_chat: bool
    summary_text: str | None
    workspace_summary: str
    messages: list[AssistantMessageResponse]
    latest_resume_revision: ResumeRevisionRecordResponse | None = None
    knowledge_document_count: int = 0
    knowledge_chunk_count: int = 0


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户在助手页输入的问题")


class AssistantChatResponse(BaseModel):
    thread_id: int
    job_id: int
    message: AssistantMessageResponse
    summary_text: str | None
    workspace_summary: str


class KnowledgeDocumentSummaryResponse(BaseModel):
    id: int
    source_type: str
    source_key: str | None = None
    title: str
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class JobKnowledgeResponse(BaseModel):
    knowledge_base_id: int
    job_id: int
    document_count: int
    chunk_count: int
    documents: list[KnowledgeDocumentSummaryResponse]


class JobKnowledgeReindexResponse(BaseModel):
    knowledge_base_id: int
    job_id: int
    document_count: int
    chunk_count: int


class InterviewKnowledgeImportItem(BaseModel):
    source_id: str | None = None
    url: str | None = None
    title: str | None = None
    author_name: str | None = None
    published_at: str | None = None
    crawl_at: str | None = None
    company: str | None = None
    role: str | None = None
    interview_stage: str | None = None
    city: str | None = None
    tags: list[str] = []
    quality_score: int | None = None
    content_raw: str = Field(..., min_length=20)
    content_summary: str | None = None
    metadata: dict | None = None


class InterviewKnowledgeImportRequest(BaseModel):
    items: list[InterviewKnowledgeImportItem] = Field(..., min_length=1)


class InterviewKnowledgeSourceResponse(BaseModel):
    id: int
    source_platform: str
    source_type: str
    source_id: str | None = None
    url: str | None = None
    title: str | None = None
    author_name: str | None = None
    published_at: str | None = None
    crawl_at: str | None = None
    ingest_at: str | None = None
    company: str | None = None
    role: str | None = None
    interview_stage: str | None = None
    city: str | None = None
    tags: list[str] = []
    quality_score: int | None = None
    compliance_status: str
    content_clean: str
    content_summary: str
    updated_at: str | None = None
    chunk_count: int = 0
    embedding_ready: bool = False


class InterviewKnowledgeImportResponse(BaseModel):
    imported_count: int
    source_platform: str
    compliance_status: str
    sources: list[InterviewKnowledgeSourceResponse]


class InterviewKnowledgeSourceListResponse(BaseModel):
    total_count: int
    sources: list[InterviewKnowledgeSourceResponse]


class InterviewKnowledgeCompileLinksRequest(BaseModel):
    links: list[str] = Field(..., min_length=1)
    default_company: str | None = None
    default_role: str | None = None
    default_city: str | None = None
    compliance_status: str | None = None


class InterviewKnowledgeCompileResult(BaseModel):
    url: str
    status: str
    error: str | None = None
    source_id: str | None = None
    title: str | None = None
    company: str | None = None
    role: str | None = None
    interview_stage: str | None = None
    city: str | None = None
    content_summary: str | None = None


class InterviewKnowledgeCompileLinksResponse(BaseModel):
    requested_count: int
    compiled_count: int
    imported_count: int
    failed_count: int
    results: list[InterviewKnowledgeCompileResult]


class InterviewKnowledgeSearchResponseItem(BaseModel):
    source_record_id: int
    source_platform: str
    source_type: str
    source_id: str | None = None
    url: str | None = None
    title: str | None = None
    company: str | None = None
    role: str | None = None
    interview_stage: str | None = None
    city: str | None = None
    content_summary: str
    chunk_text: str
    score: float
    compliance_status: str


class InterviewKnowledgeSearchResponse(BaseModel):
    query: str
    result_count: int
    results: list[InterviewKnowledgeSearchResponseItem]


class InterviewKnowledgeReindexResponse(BaseModel):
    knowledge_base_job_id: int
    source_count: int
    document_count: int
    chunk_count: int


class AssistantRagSearchRequest(BaseModel):
    message: str = Field(..., min_length=1)
    company: str | None = None
    role: str | None = None
    interview_stage: str | None = None
    city: str | None = None
    top_k: int = 4


class AssistantRagSearchResponse(BaseModel):
    message: str
    context: str
    result_count: int
    results: list[InterviewKnowledgeSearchResponseItem]
