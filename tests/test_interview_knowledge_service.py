from app.schemas import InterviewKnowledgeImportItem
from app.services.interview_knowledge_service import (
    assistant_rag_search,
    build_interview_rag_context,
    import_manual_knowledge,
    search_interview_knowledge,
)


def test_import_manual_knowledge_creates_searchable_records(db_session):
    response = import_manual_knowledge(
        db_session,
        [
            InterviewKnowledgeImportItem(
                source_id="note-100",
                url="https://www.xiaohongshu.com/explore/note-100",
                title="Alibaba PM interview",
                company="阿里",
                role="产品经理",
                interview_stage="一面",
                city="杭州",
                tags=["阿里", "产品经理"],
                content_raw="阿里产品经理一面主要问用户研究、数据分析和项目复盘，还问了反问问题和业务理解。",
            )
        ],
    )
    assert response.imported_count == 1
    assert response.sources[0].company == "阿里"
    assert response.sources[0].content_summary

    search = search_interview_knowledge(db_session, "阿里产品经理一面问什么", company="阿里", role="产品经理")
    assert search.result_count >= 1
    assert search.results[0].company == "阿里"


def test_interview_rag_context_and_assistant_search(db_session):
    import_manual_knowledge(
        db_session,
        [
            InterviewKnowledgeImportItem(
                source_id="note-200",
                url="https://www.xiaohongshu.com/explore/note-200",
                title="Tencent backend second round",
                company="腾讯",
                role="后端开发",
                interview_stage="二面",
                city="深圳",
                tags=["腾讯", "后端"],
                content_raw="腾讯后端开发二面会重点追问系统设计、MySQL 索引、Redis 缓存和项目中的性能优化。",
            )
        ],
    )

    context = build_interview_rag_context(
        db_session,
        "腾讯后端开发二面会问什么",
        company="腾讯",
        role="后端开发",
    )
    assert "腾讯" in context
    assert "来源:" in context

    rag = assistant_rag_search(
        db_session,
        "腾讯后端开发二面会问什么",
        company="腾讯",
        role="后端开发",
    )
    assert rag.result_count >= 1
    assert rag.results[0].company == "腾讯"


def test_search_interview_knowledge_deduplicates_chunks_by_source(db_session):
    import_response = import_manual_knowledge(
        db_session,
        [
            InterviewKnowledgeImportItem(
                source_id="note-300",
                url="https://www.xiaohongshu.com/explore/note-300",
                title="Alibaba PM notes",
                company="阿里",
                role="产品经理",
                interview_stage="二面",
                city="杭州",
                tags=["阿里", "产品经理"],
                content_raw=(
                    "阿里产品经理二面偏业务理解和深入追问。"
                    "阿里产品经理二面更关注业务理解、数据分析和项目推进，追问会比较深入。"
                    "如果问到项目复盘，要把目标、策略、结果和反思讲清楚。"
                    "另外还会追问跨团队协作、指标拆解和优先级判断。"
                ),
            )
        ],
    )
    assert import_response.imported_count == 1

    search = search_interview_knowledge(db_session, "阿里产品经理二面业务理解和深入追问", company="阿里", role="产品经理")

    assert search.result_count == 1
    assert len(search.results) == 1
    assert search.results[0].source_id == "note-300"
    assert "业务理解" in search.results[0].chunk_text


def test_search_interview_knowledge_uses_best_scoring_chunk_for_preview(db_session):
    import_response = import_manual_knowledge(
        db_session,
        [
            InterviewKnowledgeImportItem(
                source_id="note-301",
                url="https://www.xiaohongshu.com/explore/note-301",
                title="Meituan PM first round",
                company="美团",
                role="产品经理",
                interview_stage="一面",
                city="北京",
                tags=["美团", "产品经理"],
                content_raw=(
                    "美团产品经理一面先做自我介绍，然后简单聊过往经历。"
                    "美团产品经理一面重点问用户增长、北极星指标、需求拆解和AB测试。"
                    "后面还会追问你如何推动复杂项目落地，以及如何和研发协作。"
                    "最后通常会留时间给候选人反问。"
                ),
            )
        ],
    )
    assert import_response.imported_count == 1

    search = search_interview_knowledge(
        db_session,
        "美团产品经理一面用户增长 北极星指标 AB测试",
        company="美团",
        role="产品经理",
    )

    assert search.result_count == 1
    assert "用户增长" in search.results[0].chunk_text


def test_search_interview_knowledge_allows_fuzzy_role_matching(db_session):
    import_response = import_manual_knowledge(
        db_session,
        [
            InterviewKnowledgeImportItem(
                source_id="note-302",
                url="https://www.xiaohongshu.com/explore/note-302",
                title="PM interview notes",
                company="美团",
                role="产品经理",
                interview_stage="一面",
                city="北京",
                tags=["美团", "产品经理"],
                content_raw=(
                    "美团产品经理一面先做自我介绍，然后围绕用户增长、需求拆解和跨团队协作深入追问。"
                    "面试官还会问你如何定义北极星指标、如何拆分目标，以及遇到资源冲突时怎么推进项目。"
                ),
            )
        ],
    )
    assert import_response.imported_count == 1

    search = search_interview_knowledge(db_session, "AI产品经理一面问什么", company="美团", role="AI产品经理")

    assert search.result_count == 1
    assert search.results[0].role == "产品经理"


def test_search_interview_knowledge_deduplicates_logical_source_duplicates(db_session):
    shared_payload = dict(
        source_id="note-dup-001",
        url="https://www.xiaohongshu.com/explore/note-dup-001",
        title="Alibaba PM duplicate notes",
        company="阿里",
        role="产品经理",
        interview_stage="二面",
        city="杭州",
        tags=["阿里", "产品经理"],
        content_raw=(
            "阿里产品经理二面更关注业务理解、数据分析和项目推进，追问会比较深入。"
            "如果问到项目复盘，要把目标、策略、结果和反思讲清楚。"
        ),
    )

    import_manual_knowledge(db_session, [InterviewKnowledgeImportItem(**shared_payload)])
    import_manual_knowledge(db_session, [InterviewKnowledgeImportItem(**shared_payload)])

    search = search_interview_knowledge(db_session, "阿里产品经理二面问什么", company="阿里", role="产品经理")

    assert search.result_count == 1
    assert len(search.results) == 1
    assert search.results[0].source_id == "note-dup-001"
