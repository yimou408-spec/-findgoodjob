from sqlalchemy.orm import Session

from app.db.models.resume_revision import ResumeRevision


class RevisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, job_description_id: int, resume_id: int, revised_content: str, rationale: str) -> ResumeRevision:
        obj = ResumeRevision(
            job_description_id=job_description_id,
            resume_id=resume_id,
            revised_content=revised_content,
            rationale=rationale,
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj
