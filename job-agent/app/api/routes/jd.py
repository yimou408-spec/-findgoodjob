from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.jd import JDCreate, JDOut
from app.services.jd_service import JDService

router = APIRouter(prefix="/jds", tags=["jd"])


@router.post("", response_model=JDOut)
def create_jd(payload: JDCreate, db: Session = Depends(get_db)):
    return JDService(db).create_jd(payload)


@router.get("", response_model=list[JDOut])
def list_jd(keyword: str | None = Query(None), db: Session = Depends(get_db)):
    return JDService(db).search(keyword=keyword)


@router.get("/{jd_id}", response_model=JDOut)
def get_jd(jd_id: int, db: Session = Depends(get_db)):
    jd = JDService(db).get_jd(jd_id)
    if not jd:
        raise ValueError("JD not found")
    return jd
