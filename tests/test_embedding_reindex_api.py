def test_reindex_interview_knowledge_endpoint(client):
    import_response = client.post(
        "/knowledge/import/manual",
        json={
            "items": [
                {
                    "source_id": "note-reindex-001",
                    "url": "https://www.xiaohongshu.com/explore/note-reindex-001",
                    "title": "Reindex PM interview",
                    "company": "阿里",
                    "role": "产品经理",
                    "interview_stage": "二面",
                    "city": "杭州",
                    "tags": ["阿里", "产品经理"],
                    "content_raw": "阿里产品经理二面会重点追问业务理解、数据分析和项目推进。",
                }
            ]
        },
    )
    assert import_response.status_code == 200

    response = client.post("/knowledge/reindex")

    assert response.status_code == 200
    data = response.json()
    assert "source_count" in data
    assert "document_count" in data
    assert "chunk_count" in data
