from sqlalchemy.orm import Session

from app.db.models.resume import Resume


class ResumeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, content: str) -> Resume:
        obj = Resume(content=content)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj
