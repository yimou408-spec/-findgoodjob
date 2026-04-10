from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.job_description import JobDescription


class JDRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, title: str, company: str, content: str, source: str | None = None) -> JobDescription:
        obj = JobDescription(title=title, company=company, content=content, source=source)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get(self, jd_id: int) -> JobDescription | None:
        return self.db.get(JobDescription, jd_id)

    def list(self, keyword: str | None = None) -> list[JobDescription]:
        stmt = select(JobDescription).order_by(JobDescription.id.desc())
        if keyword:
            stmt = stmt.where(JobDescription.content.contains(keyword) | JobDescription.title.contains(keyword))
        return list(self.db.scalars(stmt).all())
