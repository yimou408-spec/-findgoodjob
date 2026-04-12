import json
import logging
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, File, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import AppError
from app.schemas import (
    AssistantRagSearchRequest,
    AssistantRagSearchResponse,
    AssistantChatRequest,
    AssistantThreadResponse,
    AnalyzeJobResponse,
    InterviewKnowledgeCompileLinksRequest,
    InterviewKnowledgeCompileLinksResponse,
    InterviewKnowledgeImportRequest,
    InterviewKnowledgeImportResponse,
    InterviewKnowledgeReindexResponse,
    InterviewKnowledgeSearchResponse,
    InterviewKnowledgeSourceListResponse,
    JobCreate,
    JobKnowledgeReindexResponse,
    JobKnowledgeResponse,
    JobResponse,
    JobUpdate,
    ResumeDocumentParseResponse,
    ResumeRevisionRequest,
    ResumeRevisionResponse,
)
from app.services.interview_knowledge_service import (
    assistant_rag_search,
    import_manual_knowledge,
    import_xiaohongshu_research_knowledge,
    list_interview_knowledge_sources,
    reindex_interview_knowledge,
    search_interview_knowledge,
)
from app.services.xiaohongshu_compile_service import compile_xiaohongshu_links
from app.services.assistant_service import (
    get_assistant_thread_state,
    get_job_knowledge_state,
    reindex_job_knowledge,
    stream_assistant_chat,
)
from app.services.document_service import extract_text_from_upload
from app.services.jd_service import (
    analyze_job,
    create_job,
    delete_job,
    get_job_or_404,
    list_jobs,
    stream_analyze_job,
    update_job,
)
from app.services.resume_service import (
    revise_resume_for_job,
    save_resume_revision_record,
    stream_resume_revision_for_job,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("findgoodjob.app")

app = FastAPI(
    title="FindGoodJob Agent",
    version="0.1.0",
    description="用于岗位 JD 入库、岗位分析、简历修订和 AI 求职助手的后端服务。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def log_startup() -> None:
    logger.info("FindGoodJob backend started")


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error_code": exc.error_code},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "请求参数不合法",
            "errors": exc.errors(),
            "error_code": "validation_error",
        },
    )


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _wrap_stream(generator: AsyncIterator[dict]) -> AsyncIterator[str]:
    try:
        async for event in generator:
            yield _sse_event(event)
    except AppError as exc:
        yield _sse_event({"type": "error", "detail": exc.message, "error_code": exc.error_code})
    except Exception as exc:  # pragma: no cover
        logger.exception("streaming endpoint failed")
        yield _sse_event({"type": "error", "detail": str(exc), "error_code": "stream_error"})


@app.get("/health", summary="健康检查", description="检查服务是否正常启动。")
def health_check():
    return {"status": "ok"}


@app.get("/jobs", response_model=list[JobResponse], summary="岗位列表", description="返回数据库中的岗位列表。")
def list_jobs_endpoint(db: Session = Depends(get_db)):
    return list_jobs(db)


@app.post("/jobs", response_model=JobResponse, summary="新增岗位", description="创建一条岗位 JD 记录。")
def create_job_endpoint(payload: JobCreate, db: Session = Depends(get_db)):
    return create_job(db, payload)


@app.put("/jobs/{job_id}", response_model=JobResponse, summary="更新岗位", description="根据岗位 ID 更新岗位信息。")
def update_job_endpoint(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)):
    return update_job(db, job_id, payload)


@app.get("/jobs/{job_id}", response_model=JobResponse, summary="查询岗位", description="根据岗位 ID 获取岗位详情。")
def get_job_endpoint(job_id: int, db: Session = Depends(get_db)):
    return get_job_or_404(db, job_id)


@app.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除岗位",
    description="根据岗位 ID 删除岗位记录。",
)
def delete_job_endpoint(job_id: int, db: Session = Depends(get_db)):
    delete_job(db, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/resume/parse-document",
    response_model=ResumeDocumentParseResponse,
    summary="解析简历文件",
    description="上传图片或 PDF，提取文本后返回给前端自动填入简历修订输入框。",
)
async def parse_resume_document_endpoint(file: UploadFile = File(...)):
    parsed = await extract_text_from_upload(file)
    return ResumeDocumentParseResponse(
        filename=parsed.filename,
        content_type=parsed.content_type,
        extracted_text=parsed.extracted_text,
    )


@app.post(
    "/jobs/{job_id}/analyze",
    response_model=AnalyzeJobResponse,
    summary="分析岗位 JD",
    description="对目标岗位 JD 进行结构化分析，不在此阶段输出匹配度评分。",
)
def analyze_job_endpoint(job_id: int, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    analyzed_job = analyze_job(db, job)
    return AnalyzeJobResponse(
        job_id=analyzed_job.id,
        analysis_result=analyzed_job.analysis_result or "",
        analysis_improvement_advice=analyzed_job.analysis_improvement_advice,
    )


@app.post(
    "/jobs/{job_id}/analyze/stream",
    summary="流式分析岗位 JD",
    description="流式返回岗位分析结果，结束后自动保存岗位分析摘要和改进建议。",
)
async def analyze_job_stream_endpoint(job_id: int, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    return StreamingResponse(
        _wrap_stream(stream_analyze_job(db, job)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/jobs/{job_id}/revise-resume",
    response_model=ResumeRevisionResponse,
    summary="修订简历",
    description="结合岗位 JD 和岗位分析结果，对原始简历进行定向修订并返回匹配度评分。",
)
def revise_resume_endpoint(job_id: int, payload: ResumeRevisionRequest, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    revised = revise_resume_for_job(job, payload.resume_text)
    save_resume_revision_record(db, job, payload.resume_text, revised)
    return ResumeRevisionResponse(
        job_id=job.id,
        revised_resume=revised.revised_resume,
        match_score=revised.match_score,
        match_explanation=revised.match_explanation,
    )


@app.post(
    "/jobs/{job_id}/revise-resume/stream",
    summary="流式修订简历",
    description="流式返回简历修订过程，结束后返回最终匹配度评分和修订结果。",
)
async def revise_resume_stream_endpoint(job_id: int, payload: ResumeRevisionRequest, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    return StreamingResponse(
        _wrap_stream(stream_resume_revision_for_job(job, payload.resume_text, db=db)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get(
    "/jobs/{job_id}/assistant/thread",
    response_model=AssistantThreadResponse,
    summary="获取岗位求职助手线程",
    description="返回该岗位的助手线程、工作台摘要、记忆摘要和全部历史消息。",
)
def get_assistant_thread_endpoint(job_id: int, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    return get_assistant_thread_state(db, job)


@app.post(
    "/jobs/{job_id}/assistant/chat/stream",
    summary="流式发送求职助手消息",
    description="将当前岗位工作台摘要、混合记忆和知识库检索结果注入 DeepSeek，并以 SSE 方式返回助手回复。",
)
async def assistant_chat_stream_endpoint(job_id: int, payload: AssistantChatRequest, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    return StreamingResponse(
        _wrap_stream(stream_assistant_chat(db, job, payload.message)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get(
    "/jobs/{job_id}/knowledge",
    response_model=JobKnowledgeResponse,
    summary="获取岗位知识库状态",
    description="返回当前岗位知识库中的文档和切片统计，用于后续 RAG 检索调试与验证。",
)
def get_job_knowledge_endpoint(job_id: int, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    return get_job_knowledge_state(db, job)


@app.post(
    "/jobs/{job_id}/knowledge/reindex",
    response_model=JobKnowledgeReindexResponse,
    summary="重建岗位知识库索引",
    description="重新索引当前岗位的 JD、岗位分析和最近一次简历修订结果。",
)
def reindex_job_knowledge_endpoint(job_id: int, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    return reindex_job_knowledge(db, job)


@app.post(
    "/knowledge/import/manual",
    response_model=InterviewKnowledgeImportResponse,
    summary="导入人工整理或授权面试经验",
    description="导入人工整理、授权投稿或结构化摘要形式的小红书面试经验知识。",
)
def import_manual_knowledge_endpoint(payload: InterviewKnowledgeImportRequest, db: Session = Depends(get_db)):
    return import_manual_knowledge(db, payload.items)


@app.post(
    "/knowledge/import/xiaohongshu-research",
    response_model=InterviewKnowledgeImportResponse,
    summary="导入研究抓取面试经验",
    description="导入研究用途的小红书公开面试经验数据，供内部验证知识库效果。",
)
def import_xiaohongshu_research_endpoint(payload: InterviewKnowledgeImportRequest, db: Session = Depends(get_db)):
    return import_xiaohongshu_research_knowledge(db, payload.items)


@app.post(
    "/knowledge/reindex",
    response_model=InterviewKnowledgeReindexResponse,
    summary="重建面经知识库向量",
    description="对历史面经来源重新切片并生成真正的智谱 Embedding 向量，用于升级旧伪向量数据。",
)
def reindex_interview_knowledge_endpoint(db: Session = Depends(get_db)):
    return reindex_interview_knowledge(db)


@app.get(
    "/knowledge/sources",
    response_model=InterviewKnowledgeSourceListResponse,
    summary="获取已入库面经知识列表",
    description="返回真实已入库的小红书面经知识来源列表，供知识库管理页刷新后重新读取持久化数据。",
)
def list_interview_knowledge_sources_endpoint(limit: int = 50, db: Session = Depends(get_db)):
    return list_interview_knowledge_sources(db, limit=limit)


@app.post(
    "/knowledge/compile-links/xiaohongshu",
    response_model=InterviewKnowledgeCompileLinksResponse,
    summary="编译小红书链接并写入知识库",
    description="仅抓取公开可访问的小红书页面，自动抽取正文、结构化字段并导入面试经验知识库。",
)
def compile_xiaohongshu_links_endpoint(
    payload: InterviewKnowledgeCompileLinksRequest,
    db: Session = Depends(get_db),
):
    return compile_xiaohongshu_links(
        db,
        payload.links,
        default_company=payload.default_company,
        default_role=payload.default_role,
        default_city=payload.default_city,
        compliance_status=payload.compliance_status,
    )


@app.get(
    "/knowledge/search",
    response_model=InterviewKnowledgeSearchResponse,
    summary="搜索小红书面试经验知识库",
    description="按 query 和可选过滤条件检索小红书面试经验向量知识库。",
)
def search_knowledge_endpoint(
    query: str,
    company: str | None = None,
    role: str | None = None,
    interview_stage: str | None = None,
    city: str | None = None,
    top_k: int = 4,
    db: Session = Depends(get_db),
):
    return search_interview_knowledge(
        db,
        query,
        company=company,
        role=role,
        interview_stage=interview_stage,
        city=city,
        top_k=top_k,
    )


@app.post(
    "/assistant/rag/search",
    response_model=AssistantRagSearchResponse,
    summary="给助手使用的面试经验 RAG 检索",
    description="根据用户问题和过滤条件搜索小红书面试经验知识库，并返回可注入助手的上下文。",
)
def assistant_rag_search_endpoint(payload: AssistantRagSearchRequest, db: Session = Depends(get_db)):
    return assistant_rag_search(
        db,
        payload.message,
        company=payload.company,
        role=payload.role,
        interview_stage=payload.interview_stage,
        city=payload.city,
        top_k=payload.top_k,
    )
