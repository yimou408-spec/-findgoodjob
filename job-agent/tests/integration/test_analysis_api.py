from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analysis_api():
    payload = {
        "title": "Backend Engineer",
        "company": "ACME",
        "content": "Need SQL, APIs, Python, and ownership.",
    }
    jd = client.post("/jds", json=payload).json()
    resp = client.post("/analysis", json={"jd_id": jd["id"]})
    assert resp.status_code == 200
    assert "summary" in resp.json()
