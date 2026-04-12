from app.services import xiaohongshu_compile_service


VALID_HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "headline": "美团产品经理一面面经",
        "articleBody": "美团产品经理一面主要问用户增长、需求拆解、竞品分析，还会让你做反问。",
        "author": {"name": "候选人A"},
        "datePublished": "2026-04-10T10:00:00+08:00"
      }
    </script>
  </head>
  <body></body>
</html>
"""


def test_compile_xiaohongshu_links_endpoint_and_search(client, monkeypatch):
    def fake_fetch_public_page(url: str) -> str:
        if url.endswith("note-001"):
            return VALID_HTML
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(xiaohongshu_compile_service, "fetch_public_page", fake_fetch_public_page)

    response = client.post(
        "/knowledge/compile-links/xiaohongshu",
        json={
            "links": ["https://www.xiaohongshu.com/explore/note-001"],
            "default_company": "美团",
            "default_role": "产品经理",
            "default_city": "北京",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requested_count"] == 1
    assert data["compiled_count"] == 1
    assert data["imported_count"] == 1
    assert data["failed_count"] == 0
    assert data["results"][0]["status"] == "imported"
    assert data["results"][0]["company"] == "美团"

    search_response = client.get(
        "/knowledge/search",
        params={"query": "美团产品经理一面问什么", "company": "美团", "role": "产品经理"},
    )
    assert search_response.status_code == 200
    search_data = search_response.json()
    assert search_data["result_count"] >= 1
    assert search_data["results"][0]["url"] == "https://www.xiaohongshu.com/explore/note-001"


def test_compile_xiaohongshu_links_strips_query_params(client, monkeypatch):
    called_urls: list[str] = []

    def fake_fetch_public_page(url: str) -> str:
        called_urls.append(url)
        return VALID_HTML

    monkeypatch.setattr(xiaohongshu_compile_service, "fetch_public_page", fake_fetch_public_page)

    response = client.post(
        "/knowledge/compile-links/xiaohongshu",
        json={
            "links": [
                "https://www.xiaohongshu.com/explore/69b90e86000000001a026898?xsec_token=abc&xsec_source=pc_search&source=web_explore_feed"
            ],
            "default_company": "美团",
            "default_role": "产品经理",
        },
    )

    assert response.status_code == 200
    assert called_urls == ["https://www.xiaohongshu.com/explore/69b90e86000000001a026898"]


def test_compile_xiaohongshu_links_endpoint_returns_mixed_results(client, monkeypatch):
    def fake_fetch_public_page(url: str) -> str:
        if url.endswith("note-good"):
            return VALID_HTML
        if url.endswith("note-empty"):
            return "<html><head><title>空页面</title></head><body></body></html>"
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(xiaohongshu_compile_service, "fetch_public_page", fake_fetch_public_page)

    response = client.post(
        "/knowledge/compile-links/xiaohongshu",
        json={
            "links": [
                "https://www.xiaohongshu.com/explore/note-good",
                "https://www.xiaohongshu.com/explore/note-empty",
                "https://example.com/not-xiaohongshu",
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requested_count"] == 3
    assert data["compiled_count"] == 1
    assert data["imported_count"] == 1
    assert data["failed_count"] == 2
    assert [item["status"] for item in data["results"]] == ["imported", "failed", "failed"]
    assert data["results"][1]["error"] in {"content_unavailable", "not_interview_experience"}
    assert data["results"][2]["error"] == "invalid_domain"
