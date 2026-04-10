from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResumeRevision(Base):
    __tablename__ = "resume_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_description_id: Mapped[int] = mapped_column(ForeignKey("job_descriptions.id"), nullable=False)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    revised_content: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
