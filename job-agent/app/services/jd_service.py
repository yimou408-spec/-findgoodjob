from sqlalchemy.orm import Session

from app.db.repositories.jd_repo import JDRepository
from app.schemas.jd import JDCreate


class JDService:
    def __init__(self, db: Session):
        self.repo = JDRepository(db)

    def create_jd(self, payload: JDCreate):
        return self.repo.create(
            title=payload.title,
            company=payload.company,
            content=payload.content,
            source=payload.source,
        )

    def get_jd(self, jd_id: int):
        return self.repo.get(jd_id)

    def search(self, keyword: str | None = None):
        return self.repo.list(keyword=keyword)
