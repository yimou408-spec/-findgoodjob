from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.resume import ResumeRewriteRequest, ResumeRewriteResponse
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/rewrite", response_model=ResumeRewriteResponse)
def rewrite_resume(payload: ResumeRewriteRequest, db: Session = Depends(get_db)):
    revision = ResumeService(db).rewrite(jd_id=payload.jd_id, resume_content=payload.resume_content)
    return {
        "revision_id": revision.id,
        "jd_id": payload.jd_id,
        "revised_content": revision.revised_content,
        "rationale": revision.rationale,
    }
