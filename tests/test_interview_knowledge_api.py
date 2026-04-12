def test_import_manual_interview_knowledge_and_search(client):
    payload = {
        "items": [
            {
                "source_id": "note-001",
                "url": "https://www.xiaohongshu.com/explore/note-001",
                "title": "美团产品经理一面面经",
                "author_name": "候选人A",
                "company": "美团",
                "role": "产品经理",
                "interview_stage": "一面",
                "city": "北京",
                "tags": ["产品经理", "面经"],
                "content_raw": "美团产品经理一面，主要问了用户增长、需求拆解、竞品分析。最后还问了反问问题。",
            }
        ]
    }

    import_response = client.post("/knowledge/import/manual", json=payload)
    assert import_response.status_code == 200
    import_data = import_response.json()
    assert import_data["imported_count"] == 1
    assert import_data["sources"][0]["chunk_count"] >= 1
    assert import_data["sources"][0]["embedding_ready"] is True

    search_response = client.get(
        "/knowledge/search",
        params={"query": "美团产品经理一面问什么", "company": "美团", "role": "产品经理"},
    )
    assert search_response.status_code == 200
    search_data = search_response.json()
    assert search_data["result_count"] >= 1
    assert search_data["results"][0]["company"] == "美团"
    assert search_data["results"][0]["url"] == "https://www.xiaohongshu.com/explore/note-001"

    list_response = client.get("/knowledge/sources", params={"limit": 10})
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["total_count"] >= 1
    assert list_data["sources"][0]["chunk_count"] >= 1
    assert list_data["sources"][0]["embedding_ready"] is True


def test_import_research_interview_knowledge_and_assistant_rag_search(client):
    payload = {
        "items": [
            {
                "source_id": "note-002",
                "url": "https://www.xiaohongshu.com/explore/note-002",
                "title": "字节算法岗 HR 面经验",
                "company": "字节",
                "role": "算法工程师",
                "interview_stage": "HR 面",
                "city": "上海",
                "tags": ["算法", "HR面"],
                "content_raw": "字节算法岗 HR 面，主要聊了实习经历、转正意愿、薪资预期和城市选择，也问了为什么想来字节。",
            }
        ]
    }

    import_response = client.post("/knowledge/import/xiaohongshu-research", json=payload)
    assert import_response.status_code == 200
    assert import_response.json()["imported_count"] == 1

    rag_response = client.post(
        "/assistant/rag/search",
        json={
            "message": "字节算法岗 HR 面一般会聊什么",
            "company": "字节",
            "role": "算法工程师",
            "interview_stage": "HR 面",
        },
    )
    assert rag_response.status_code == 200
    data = rag_response.json()
    assert data["result_count"] >= 1
    assert "字节" in data["context"]
    assert data["results"][0]["interview_stage"] == "HR 面"
