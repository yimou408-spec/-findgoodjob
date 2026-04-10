from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_and_get_jd():
    payload = {
        "title": "LLM Engineer",
        "company": "ACME",
        "content": "Need Python, FastAPI, LangChain and strong communication skills.",
    }
    created = client.post("/jds", json=payload)
    assert created.status_code == 200
    jd_id = created.json()["id"]

    got = client.get(f"/jds/{jd_id}")
    assert got.status_code == 200
    assert got.json()["title"] == "LLM Engineer"
