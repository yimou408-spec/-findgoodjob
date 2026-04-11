from io import BytesIO

from app.services import jd_service, resume_service
from app.services.document_service import MAX_UPLOAD_SIZE_BYTES


def create_job_payload():
    return {
        "title": "AI Agent 开发工程师",
        "company": "测试公司",
        "source": "Boss直聘",
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
            "source": "LinkedIn",
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


def test_validation_error_for_short_jd(client):
    payload = create_job_payload()
    payload["jd_text"] = "太短了"
    response = client.post("/jobs", json=payload)
    assert response.status_code == 422
    assert response.json()["error_code"] == "validation_error"
