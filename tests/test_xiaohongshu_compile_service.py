from app.exceptions import AppError
from app.services.xiaohongshu_compile_service import (
    compile_note_to_import_item,
    extract_note_payload,
    fetch_public_page,
)


def test_extract_note_payload_from_ld_json():
    html = """
    <html>
      <head>
        <title>小红书面经</title>
        <script type="application/ld+json">
          {
            "headline": "美团产品经理一面面经",
            "articleBody": "美团产品经理一面主要会问用户增长、需求拆解和反问问题。",
            "author": {"name": "候选人A"},
            "datePublished": "2026-04-10T10:00:00+08:00"
          }
        </script>
      </head>
      <body></body>
    </html>
    """

    payload = extract_note_payload(html, "https://www.xiaohongshu.com/explore/note-100")

    assert payload["title"] == "美团产品经理一面面经"
    assert "用户增长" in payload["content_raw"]
    assert payload["author_name"] == "候选人A"
    assert payload["published_at"] == "2026-04-10T10:00:00+08:00"


def test_compile_note_to_import_item_rejects_non_interview_text():
    payload = {
        "url": "https://www.xiaohongshu.com/explore/note-101",
        "title": "今日穿搭分享",
        "content_raw": "今天分享一下春季穿搭、包包和拍照滤镜，没有面试内容。",
        "author_name": "博主A",
        "published_at": None,
    }

    try:
        compile_note_to_import_item(payload)
    except AppError as exc:
        assert exc.error_code == "not_interview_experience"
    else:
        raise AssertionError("expected not_interview_experience")


def test_extract_note_payload_from_meta_description():
    html = """
    <html>
      <head>
        <meta property="og:title" content="腾讯后端开发二面面经" />
        <meta property="og:description" content="腾讯后端开发二面主要问系统设计、MySQL 索引、Redis 缓存和项目压测经验。" />
      </head>
      <body></body>
    </html>
    """

    payload = extract_note_payload(html, "https://www.xiaohongshu.com/explore/note-102")

    assert payload["title"] == "腾讯后端开发二面面经"
    assert "系统设计" in payload["content_raw"]


def test_extract_note_payload_from_script_escaped_content():
    html = """
    <html>
      <head></head>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "note": {
              "title": "\\u5b57\\u8282\\u4ea7\\u54c1\\u7ecf\\u7406\\u4e00\\u9762\\u9762\\u7ecf",
              "desc": "\\u5b57\\u8282\\u4ea7\\u54c1\\u7ecf\\u7406\\u4e00\\u9762\\u4e3b\\u8981\\u95ee\\u7528\\u6237\\u589e\\u957f\\u3001\\u7ade\\u54c1\\u5206\\u6790\\u3001\\u9879\\u76ee\\u63a8\\u8fdb\\uff0c\\u8fd8\\u4f1a\\u8ba9\\u4f60\\u505a\\u53cd\\u95ee\\u3002"
            }
          }
        </script>
      </body>
    </html>
    """

    payload = extract_note_payload(html, "https://www.xiaohongshu.com/explore/note-103")

    assert "字节产品经理一面面经" == payload["title"]
    assert "用户增长" in payload["content_raw"]


def test_fetch_public_page_rejects_restricted_xiaohongshu_note(monkeypatch):
    class FakeResponse:
      status_code = 200
      url = "https://www.xiaohongshu.com/404?error_code=300031"
      text = "<html><body>当前笔记暂时无法浏览</body></html>"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, _url):
            return FakeResponse()

    monkeypatch.setattr("app.services.xiaohongshu_compile_service.httpx.Client", FakeClient)

    try:
        fetch_public_page("https://www.xiaohongshu.com/explore/note-104")
    except AppError as exc:
        assert exc.error_code == "http_forbidden"
    else:
        raise AssertionError("expected http_forbidden")
