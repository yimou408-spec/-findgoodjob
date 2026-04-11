from types import SimpleNamespace

import pytest

from app.exceptions import ModelInvocationError, NotFoundError
from app.schemas import JobCreate, ResumeRevisionRequest
from app.services import jd_service, resume_service


class FakeAgent:
    def invoke(self, payload):
        return {
            "improvement_advice": ["突出项目结果", "补充关键技术关键词"],
            "analysis_result": f"模拟岗位分析摘要：{payload['input'][:12]}",
        }


class FakeStructuredRunnable:
    def __init__(self, parsed=None, parsing_error=None, raw=None):
        self.parsed = parsed
        self.parsing_error = parsing_error
        self.raw = raw

    def __call__(self, _payload):
        return {
            "parsed": self.parsed,
            "parsing_error": self.parsing_error,
            "raw": self.raw,
        }


class FakeRawMessage:
    def __init__(self, content: str, finish_reason: str = "stop"):
        self.content = content
        self.response_metadata = {"finish_reason": finish_reason}


class FakeLLM:
    def bind(self, **_kwargs):
        return self

    def with_structured_output(self, schema, **_kwargs):
        parsed = schema(
            match_score=91,
            match_explanation="当前简历已经覆盖大部分核心职责。",
            revised_resume="模拟简历修订结果",
        )
        return FakeStructuredRunnable(parsed=parsed)


def test_job_create_schema_validation():
    with pytest.raises(Exception):
        JobCreate(title="开发", company="测试", jd_text="太短了")


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
            jd_text="岗位职责：使用 LangChain 和 Python 构建 Agent 系统，熟悉 RAG 和 FastAPI。",
        ),
    )
    monkeypatch.setattr(jd_service, "llm_available", lambda: False)
    analyzed_job = jd_service.analyze_job(db_session, job)
    assert "岗位核心职责" in analyzed_job.analysis_result
    assert analyzed_job.analysis_model == "fallback"
    assert analyzed_job.analysis_match_score is None
    assert analyzed_job.analysis_improvement_advice


def test_analyze_job_with_mock_llm(db_session, monkeypatch):
    job = jd_service.create_job(
        db_session,
        JobCreate(
            title="AI Agent 开发工程师",
            company="测试公司",
            jd_text="岗位职责：使用 LangChain 和 Python 构建 Agent 系统，熟悉 RAG 和 FastAPI。",
        ),
    )
    monkeypatch.setattr(jd_service, "llm_available", lambda: True)
    monkeypatch.setattr(jd_service, "build_job_analysis_agent", lambda: FakeAgent())
    analyzed_job = jd_service.analyze_job(db_session, job)
    assert analyzed_job.analysis_result.startswith("模拟岗位分析摘要")
    assert analyzed_job.analysis_match_score is None
    assert "突出项目结果" in analyzed_job.analysis_improvement_advice


def test_revise_resume_with_fallback(monkeypatch):
    monkeypatch.setattr(resume_service, "llm_available", lambda: False)
    job = SimpleNamespace(title="AI Agent 开发工程师", jd_text="熟悉 Python、FastAPI、DeepSeek", analysis_result=None)
    result = resume_service.revise_resume_for_job(job, "3 年 Python 后端开发经验，熟悉 FastAPI。")
    assert "岗位匹配度判断" in result.revised_resume
    assert result.match_score is not None
    assert result.match_explanation


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
    assert result.revised_resume == "模拟简历修订结果"
    assert result.match_score == 91
    assert "核心职责" in result.match_explanation


def test_revise_resume_structured_output_failure(monkeypatch):
    class BrokenStructuredLLM:
        def bind(self, **_kwargs):
            return self

        def with_structured_output(self, _schema, **_kwargs):
            return FakeStructuredRunnable(
                parsed=None,
                parsing_error=ValueError("invalid json"),
                raw=FakeRawMessage("这是一段普通文本输出", finish_reason="stop"),
            )

    monkeypatch.setattr(resume_service, "llm_available", lambda: True)
    monkeypatch.setattr(resume_service, "build_llm", lambda: BrokenStructuredLLM())
    job = SimpleNamespace(
        title="AI Agent 开发工程师",
        company="测试公司",
        jd_text="熟悉 Python、FastAPI、DeepSeek",
        analysis_result="已有分析",
    )

    with pytest.raises(ModelInvocationError) as exc_info:
        resume_service.revise_resume_for_job(job, "3 年 Python 后端开发经验，熟悉 FastAPI。")

    assert "finish_reason=stop" in str(exc_info.value)
    assert "raw_preview=" in str(exc_info.value)


def test_revise_resume_model_error(monkeypatch):
    monkeypatch.setattr(resume_service, "llm_available", lambda: True)

    class BrokenLLM:
        def bind(self, **_kwargs):
            return self

        def with_structured_output(self, *_args, **_kwargs):
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
