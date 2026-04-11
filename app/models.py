from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    source = Column(String(255), nullable=True)
    jd_text = Column(Text, nullable=False)
    analysis_result = Column(Text, nullable=True)
    analysis_match_score = Column(Integer, nullable=True)
    analysis_improvement_advice = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="created", server_default="created")
    analysis_model = Column(String(100), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
