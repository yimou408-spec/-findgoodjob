import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import AppError
from app.schemas import (
    AnalyzeJobResponse,
    JobCreate,
    JobResponse,
    ResumeRevisionRequest,
    ResumeRevisionResponse,
)
from app.services.jd_service import analyze_job, create_job, get_job_or_404, list_jobs
from app.services.resume_service import revise_resume_for_job

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

# 允许本地 Vite 开发服务直接访问 FastAPI，便于前后端联调。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def log_startup() -> None:
    logger.info("FindGoodJob backend started")


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    # 统一返回 detail 和 error_code，前端可以据此展示友好错误信息。
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


@app.get("/health", summary="健康检查", description="检查服务是否正常启动。")
def health_check():
    return {"status": "ok"}


@app.get("/jobs", response_model=list[JobResponse], summary="岗位列表", description="返回数据库中的岗位列表，供前端工作台展示。")
def list_jobs_endpoint(db: Session = Depends(get_db)):
    return list_jobs(db)


@app.post("/jobs", response_model=JobResponse, summary="新增岗位", description="创建一条岗位 JD 记录并写入数据库。")
def create_job_endpoint(payload: JobCreate, db: Session = Depends(get_db)):
    return create_job(db, payload)


@app.get("/jobs/{job_id}", response_model=JobResponse, summary="查询岗位", description="根据岗位 ID 获取岗位详情。")
def get_job_endpoint(job_id: int, db: Session = Depends(get_db)):
    return get_job_or_404(db, job_id)


@app.post(
    "/jobs/{job_id}/analyze",
    response_model=AnalyzeJobResponse,
    summary="分析岗位 JD",
    description="对数据库中的目标岗位 JD 进行结构化分析。",
)
def analyze_job_endpoint(job_id: int, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    analysis = analyze_job(db, job)
    return AnalyzeJobResponse(job_id=job.id, analysis_result=analysis)


@app.post(
    "/jobs/{job_id}/revise-resume",
    response_model=ResumeRevisionResponse,
    summary="修订简历",
    description="结合岗位 JD 和岗位分析结果，对原始简历进行定向修订。",
)
def revise_resume_endpoint(
    job_id: int,
    payload: ResumeRevisionRequest,
    db: Session = Depends(get_db),
):
    job = get_job_or_404(db, job_id)
    revised_resume = revise_resume_for_job(job, payload.resume_text)
    return ResumeRevisionResponse(job_id=job.id, revised_resume=revised_resume)
