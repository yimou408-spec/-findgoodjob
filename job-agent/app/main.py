from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.routes import analysis, health, jd, resume
from app.core.config import settings
from app.core.logger import configure_logging
from app.db.base import Base
from app.db.session import engine

configure_logging()
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
register_error_handlers(app)
app.include_router(health.router)
app.include_router(jd.router)
app.include_router(analysis.router)
app.include_router(resume.router)
