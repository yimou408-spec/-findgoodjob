from types import SimpleNamespace

import pytest

from app.exceptions import ModelInvocationError, NotFoundError
from app.schemas import JobCreate, ResumeRevisionRequest
from app.services import jd_service, resume_service


class FakeAgent:
    def invoke(self, payload):
        return {"output": f"模拟分析：{payload['input'][:10]}"}


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __call__(self, payload):
        return FakeLLMResponse("模拟简历修订：测试结果")


def test_job_create_schema_validation():
    with pytest.raises(Exception):
        JobCreate(title="开发", company="测试", source="Boss", jd_text="太短了")


def test_resume_request_validation():
    with pytest.raises(Exception):
        ResumeRevisionRequest(resume_text="太短了")


def test_get_job_or_404_raises(db_session):
    with pytest.raises(NotFoundError):
        jd_service.get_job_or_404(db_session, 999)


def test_analyze_job_with_fallback(db_session, monkeypatch):
    job = jd_service.create_job(
        db_session,
        JobCreate(
            title="AI Agent 开发工程师",
            company="测试公司",
            source="Boss",
            jd_text="岗位职责：使用 LangChain 与 Python 构建 Agent 系统，熟悉 RAG 和 FastAPI。",
        ),
    )
    monkeypatch.setattr(jd_service, "llm_available", lambda: False)
    result = jd_service.analyze_job(db_session, job)
    assert "岗位核心职责" in result
    assert job.analysis_model == "fallback"


def test_analyze_job_with_mock_llm(db_session, monkeypatch):
    job = jd_service.create_job(
        db_session,
        JobCreate(
            title="AI Agent 开发工程师",
            company="测试公司",
            source="Boss",
            jd_text="岗位职责：使用 LangChain 与 Python 构建 Agent 系统，熟悉 RAG 和 FastAPI。",
        ),
    )
    monkeypatch.setattr(jd_service, "llm_available", lambda: True)
    monkeypatch.setattr(jd_service, "build_job_analysis_agent", lambda: FakeAgent())
    result = jd_service.analyze_job(db_session, job)
    assert "模拟分析" in result


def test_revise_resume_with_fallback(monkeypatch):
    monkeypatch.setattr(resume_service, "llm_available", lambda: False)
    job = SimpleNamespace(title="AI Agent 开发工程师", jd_text="熟悉 Python、FastAPI、DeepSeek", analysis_result=None)
    result = resume_service.revise_resume_for_job(job, "3 年 Python 后端开发经验，熟悉 FastAPI。")
    assert "岗位匹配度判断" in result


def test_revise_resume_with_mock_llm(monkeypatch):
    monkeypatch.setattr(resume_service, "llm_available", lambda: True)
    monkeypatch.setattr(resume_service, "build_llm", lambda: FakeLLM())
    job = SimpleNamespace(
        title="AI Agent 开发工程师",
        company="测试公司",
        jd_text="熟悉 Python、FastAPI、DeepSeek",
        analysis_result="已有分析",
    )
    result = resume_service.revise_resume_for_job(job, "3 年 Python 后端开发经验，熟悉 FastAPI。")
    assert "模拟简历修订" in result


def test_revise_resume_model_error(monkeypatch):
    monkeypatch.setattr(resume_service, "llm_available", lambda: True)

    class BrokenLLM:
        def __call__(self, payload):
            raise RuntimeError("boom")

    monkeypatch.setattr(resume_service, "build_llm", lambda: BrokenLLM())
    job = SimpleNamespace(
        title="AI Agent 开发工程师",
        company="测试公司",
        jd_text="熟悉 Python、FastAPI、DeepSeek",
        analysis_result="已有分析",
    )
    with pytest.raises(ModelInvocationError):
        resume_service.revise_resume_for_job(job, "3 年 Python 后端开发经验，熟悉 FastAPI。")
