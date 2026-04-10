from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_resume_rewrite_api():
    jd_payload = {
        "title": "Data Engineer",
        "company": "ACME",
        "content": "Need ETL, Python, SQL and cloud experience.",
    }
    jd = client.post("/jds", json=jd_payload).json()

    resp = client.post(
        "/resume/rewrite",
        json={
            "jd_id": jd["id"],
            "resume_content": "3 years Python developer, built data pipelines and REST APIs with measurable impact.",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["jd_id"] == jd["id"]
