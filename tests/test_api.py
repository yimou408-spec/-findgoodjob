from app.services import jd_service, resume_service


def create_job_payload():
    return {
        "title": "AI Agent 开发工程师",
        "company": "测试公司",
        "source": "Boss 直聘",
        "jd_text": "岗位职责：基于 LangChain 构建 Agent 系统，负责工具调用和 RAG 方案落地，熟悉 Python、FastAPI、DeepSeek。",
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


def test_get_job_not_found(client):
    response = client.get("/jobs/999")
    assert response.status_code == 404
    assert response.json()["error_code"] == "job_not_found"


def test_analyze_job_fallback(client, monkeypatch):
    monkeypatch.setattr(jd_service, "llm_available", lambda: False)
    created = client.post("/jobs", json=create_job_payload()).json()
    response = client.post(f"/jobs/{created['id']}/analyze")
    assert response.status_code == 200
    assert "岗位核心职责" in response.json()["analysis_result"]


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
    assert "岗位匹配度判断" in response.json()["revised_resume"]


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
