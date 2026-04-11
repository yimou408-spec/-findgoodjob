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
    AssistantChatRequest,
    AssistantThreadResponse,
    AnalyzeJobResponse,
    JobCreate,
    JobResponse,
    JobUpdate,
    ResumeDocumentParseResponse,
    ResumeRevisionRequest,
    ResumeRevisionResponse,
)
from app.services.assistant_service import get_assistant_thread_state, stream_assistant_chat
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
    description="用于岗位 JD 入库、岗位分析和简历定向修订的后端服务。",
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
    description="上传图片或 PDF，提取文本后返回给前端自动填充简历修订输入框。",
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
def revise_resume_endpoint(
    job_id: int,
    payload: ResumeRevisionRequest,
    db: Session = Depends(get_db),
):
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
async def revise_resume_stream_endpoint(
    job_id: int,
    payload: ResumeRevisionRequest,
    db: Session = Depends(get_db),
):
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
    description="将当前岗位工作台摘要和线程记忆注入 DeepSeek，并以 SSE 方式返回助手回复。",
)
async def assistant_chat_stream_endpoint(
    job_id: int,
    payload: AssistantChatRequest,
    db: Session = Depends(get_db),
):
    job = get_job_or_404(db, job_id)
    return StreamingResponse(
        _wrap_stream(stream_assistant_chat(db, job, payload.message)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
