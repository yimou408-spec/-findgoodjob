from sqlalchemy.orm import Session

from app.db.repositories.jd_repo import JDRepository
from app.llm.chains.jd_analyze_chain import analyze_jd


class AnalysisService:
    def __init__(self, db: Session):
        self.jd_repo = JDRepository(db)

    def analyze(self, jd_id: int) -> dict:
        jd = self.jd_repo.get(jd_id)
        if not jd:
            raise ValueError("JD not found")
        payload = analyze_jd(jd.content)
        return {
            "jd_id": jd_id,
            "summary": payload.get("summary", ""),
            "required_skills": payload.get("required_skills", []),
            "risks": payload.get("risks", []),
        }
