from io import BytesIO

from app.schemas import InterviewKnowledgeSearchResponse, InterviewKnowledgeSearchResponseItem
from app.services import assistant_service, jd_service, resume_service
from app.services.document_service import MAX_UPLOAD_SIZE_BYTES


def create_job_payload():
    return {
        "title": "AI Agent 开发工程师",
        "company": "测试公司",
        "jd_text": "岗位职责：基于 LangChain 构建 Agent 系统，负责工具调用和 RAG 方案落地，熟悉 Python、FastAPI、DeepSeek 等技术栈。",
    }


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_jobs(client):
    client.post("/jobs", json=create_job_payload())
    response = client.get("/jobs")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "AI Agent 开发工程师"


def test_create_job(client):
    response = client.post("/jobs", json=create_job_payload())
    assert response.status_code == 200
    data = response.json()
    assert data["id"] > 0
    assert data["title"] == "AI Agent 开发工程师"


def test_get_job_success(client):
    created = client.post("/jobs", json=create_job_payload()).json()
    response = client.get(f"/jobs/{created['id']}")
    assert response.status_code == 200
    assert response.json()["company"] == "测试公司"


def test_update_job(client):
    created = client.post("/jobs", json=create_job_payload()).json()
    client.post(f"/jobs/{created['id']}/analyze")

    response = client.put(
        f"/jobs/{created['id']}",
        json={
            "title": "高级 AI Agent 工程师",
            "company": "新测试公司",
            "jd_text": "负责智能体平台建设、RAG 工作流和 Prompt 工程落地，要求熟悉 Python、FastAPI、SQLAlchemy 与生产环境调优。",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "高级 AI Agent 工程师"
    assert data["company"] == "新测试公司"
    assert data["analysis_result"] is None
    assert data["analysis_improvement_advice"] is None


def test_delete_job(client):
    created = client.post("/jobs", json=create_job_payload()).json()
    response = client.delete(f"/jobs/{created['id']}")
    assert response.status_code == 204

    follow_up = client.get(f"/jobs/{created['id']}")
    assert follow_up.status_code == 404
    assert follow_up.json()["error_code"] == "job_not_found"


def test_get_job_not_found(client):
    response = client.get("/jobs/999")
    assert response.status_code == 404
    assert response.json()["error_code"] == "job_not_found"


def test_parse_resume_document_success(client, monkeypatch):
    import app.main as main_module

    async def fake_extract_text_from_upload(file):
        return main_module.ResumeDocumentParseResponse(
            filename=file.filename or "resume.pdf",
            content_type=file.content_type or "application/pdf",
            extracted_text="提取出的简历文本",
        )

    monkeypatch.setattr(main_module, "extract_text_from_upload", fake_extract_text_from_upload)

    response = client.post(
        "/resume/parse-document",
        files={"file": ("resume.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["extracted_text"] == "提取出的简历文本"


def test_parse_resume_document_rejects_unsupported_type(client):
    response = client.post(
        "/resume/parse-document",
        files={"file": ("resume.exe", BytesIO(b"not allowed"), "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "unsupported_file_type"


def test_parse_resume_document_rejects_large_file(client):
    large_bytes = b"a" * (MAX_UPLOAD_SIZE_BYTES + 1)
    response = client.post(
        "/resume/parse-document",
        files={"file": ("resume.pdf", BytesIO(large_bytes), "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["error_code"] == "file_too_large"


def test_analyze_job_fallback(client, monkeypatch):
    monkeypatch.setattr(jd_service, "llm_available", lambda: False)
    created = client.post("/jobs", json=create_job_payload()).json()
    response = client.post(f"/jobs/{created['id']}/analyze")
    assert response.status_code == 200
    data = response.json()
    assert "岗位核心职责" in data["analysis_result"]
    assert "analysis_match_score" not in data
    assert data["analysis_improvement_advice"]


def test_revise_resume_fallback(client, monkeypatch):
    monkeypatch.setattr(jd_service, "llm_available", lambda: False)
    monkeypatch.setattr(resume_service, "llm_available", lambda: False)
    created = client.post("/jobs", json=create_job_payload()).json()
    client.post(f"/jobs/{created['id']}/analyze")
    response = client.post(
        f"/jobs/{created['id']}/revise-resume",
        json={"resume_text": "3 年 Python 后端开发经验，熟悉 FastAPI、MySQL、Redis，并做过知识库项目。"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "岗位匹配度判断" in data["revised_resume"]
    assert data["match_score"] is not None
    assert data["match_explanation"]


def test_validation_error_for_short_resume(client):
    created = client.post("/jobs", json=create_job_payload()).json()
    response = client.post(f"/jobs/{created['id']}/revise-resume", json={"resume_text": "太短了"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "validation_error"


def test_get_assistant_thread_initial_state(client, monkeypatch):
    monkeypatch.setattr(assistant_service, "llm_available", lambda: False)
    created = client.post("/jobs", json=create_job_payload()).json()

    response = client.get(f"/jobs/{created['id']}/assistant/thread")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == created["id"]
    assert data["messages"] == []
    assert data["can_chat"] is False
    assert "岗位 JD" in data["workspace_summary"]
    assert data["latest_resume_revision"] is None
    assert data["knowledge_document_count"] >= 1


def test_get_assistant_thread_includes_latest_resume_revision(client, monkeypatch):
    monkeypatch.setattr(jd_service, "llm_available", lambda: False)
    monkeypatch.setattr(resume_service, "llm_available", lambda: False)
    monkeypatch.setattr(assistant_service, "llm_available", lambda: False)
    created = client.post("/jobs", json=create_job_payload()).json()
    client.post(f"/jobs/{created['id']}/analyze")
    client.post(
        f"/jobs/{created['id']}/revise-resume",
        json={"resume_text": "3 年 Python 后端经验，熟悉 FastAPI、MySQL、Redis，也做过知识库和 RAG 项目。"},
    )

    response = client.get(f"/jobs/{created['id']}/assistant/thread")

    assert response.status_code == 200
    data = response.json()
    assert data["latest_resume_revision"] is not None
    assert data["latest_resume_revision"]["revised_resume"]
    assert "最近一次简历修订输出" in data["workspace_summary"]


def test_assistant_chat_stream_persists_messages_and_cleans_markdown(client, monkeypatch):
    async def fake_stream_chat_completion(_messages, max_tokens):
        assert max_tokens == 2200
        yield "**第一段回复**"
        yield "，*第二段回复*"

    monkeypatch.setattr(assistant_service, "llm_available", lambda: True)
    monkeypatch.setattr(assistant_service, "stream_chat_completion", fake_stream_chat_completion)
    monkeypatch.setattr(assistant_service, "_summarize_thread_memory", lambda _workspace, _messages: "新的线程摘要")
    monkeypatch.setattr(
        assistant_service,
        "search_interview_knowledge",
        lambda *_args, **_kwargs: InterviewKnowledgeSearchResponse(
            query="请帮我分析这个岗位最看重什么",
            result_count=1,
            results=[
                InterviewKnowledgeSearchResponseItem(
                    source_record_id=1,
                    source_platform="xiaohongshu",
                    source_type="manual_summary",
                    source_id="note-001",
                    url="https://www.xiaohongshu.com/explore/note-001",
                    title="美团产品经理一面面经",
                    company="美团",
                    role="产品经理",
                    interview_stage="一面",
                    city="北京",
                    content_summary="美团产品经理一面重点考察用户增长、业务理解和反问。",
                    chunk_text="美团产品经理一面主要问用户增长、需求拆解和反问。",
                    score=0.9,
                    compliance_status="manual",
                )
            ],
        ),
    )

    created = client.post("/jobs", json=create_job_payload()).json()
    response = client.post(
        f"/jobs/{created['id']}/assistant/chat/stream",
        json={"message": "请帮我分析这个岗位最看重什么"},
    )

    assert response.status_code == 200
    assert '"type": "complete"' in response.text
    assert "第一段回复" in response.text
    assert "**" not in response.text

    thread_response = client.get(f"/jobs/{created['id']}/assistant/thread")
    thread_data = thread_response.json()
    assert len(thread_data["messages"]) == 2
    assert thread_data["messages"][0]["role"] == "user"
    assert thread_data["messages"][1]["role"] == "assistant"
    assert "第一段回复，第二段回复" in thread_data["messages"][1]["content"]
    assert thread_data["messages"][1]["retrieval_note"]
    assert "https://www.xiaohongshu.com/explore/note-001" in thread_data["messages"][1]["source_links"]
    assert thread_data["summary_text"] == "新的线程摘要"


def test_assistant_chat_stream_returns_error_when_llm_unavailable(client, monkeypatch):
    monkeypatch.setattr(assistant_service, "llm_available", lambda: False)
    created = client.post("/jobs", json=create_job_payload()).json()

    response = client.post(
        f"/jobs/{created['id']}/assistant/chat/stream",
        json={"message": "你好"},
    )

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert "DEEPSEEK_API_KEY" in response.text


def test_job_knowledge_endpoints(client, monkeypatch):
    monkeypatch.setattr(jd_service, "llm_available", lambda: False)
    monkeypatch.setattr(resume_service, "llm_available", lambda: False)
    created = client.post("/jobs", json=create_job_payload()).json()
    client.post(f"/jobs/{created['id']}/analyze")
    client.post(
        f"/jobs/{created['id']}/revise-resume",
        json={"resume_text": "3 年 Python 后端经验，熟悉 FastAPI、MySQL、Redis，也做过知识库和 RAG 项目。"},
    )

    get_response = client.get(f"/jobs/{created['id']}/knowledge")
    reindex_response = client.post(f"/jobs/{created['id']}/knowledge/reindex")

    assert get_response.status_code == 200
    assert get_response.json()["document_count"] >= 2
    assert get_response.json()["chunk_count"] >= 2
    assert reindex_response.status_code == 200
    assert reindex_response.json()["document_count"] >= 2


def test_validation_error_for_short_jd(client):
    payload = create_job_payload()
    payload["jd_text"] = "太短了"
    response = client.post("/jobs", json=payload)
    assert response.status_code == 422
    assert response.json()["error_code"] == "validation_error"
