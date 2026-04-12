from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlparse, urlunparse

import httpx
from sqlalchemy.orm import Session

from app.exceptions import AppError
from app.schemas import (
    InterviewKnowledgeCompileLinksResponse,
    InterviewKnowledgeCompileResult,
    InterviewKnowledgeImportItem,
)
from app.services.interview_knowledge_service import (
    _build_clean_content,
    _build_summary,
    _infer_company,
    _infer_interview_stage,
    _infer_role,
    _is_valid_interview_experience,
    import_xiaohongshu_research_knowledge,
)
from app.services.llm_output_service import normalize_model_output

XIAOHONGSHU_DOMAINS = {"xiaohongshu.com", "www.xiaohongshu.com"}
DEFAULT_COMPLIANCE_STATUS = "public_research"
REQUEST_TIMEOUT_SECONDS = 12.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _normalize_url(url: str) -> str:
    return normalize_model_output(url).strip()


def _validate_xiaohongshu_url(url: str) -> str:
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    host = (parsed.netloc or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in XIAOHONGSHU_DOMAINS:
        raise AppError(
            message="仅支持小红书公开链接。",
            status_code=400,
            error_code="invalid_domain",
        )
    canonical_path = parsed.path.rstrip("/") or parsed.path or "/"
    return urlunparse((parsed.scheme, host, canonical_path, "", "", ""))


def fetch_public_page(url: str) -> str:
    normalized = _validate_xiaohongshu_url(url)
    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            trust_env=False,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        ) as client:
            response = client.get(normalized)
    except httpx.HTTPError as exc:
        raise AppError(
            message=f"抓取小红书公开页失败: {exc}",
            status_code=502,
            error_code="fetch_failed",
        ) from exc

    if response.status_code == 403:
        raise AppError(
            message="小红书公开页返回 403，当前链接无法直接抓取。",
            status_code=403,
            error_code="http_forbidden",
        )
    if response.status_code == 404:
        raise AppError(
            message="小红书公开页不存在或已失效。",
            status_code=404,
            error_code="http_not_found",
        )
    if response.status_code >= 400:
        raise AppError(
            message=f"抓取小红书公开页失败，HTTP {response.status_code}。",
            status_code=502,
            error_code="fetch_failed",
        )
    final_url = str(response.url)
    response_text = response.text
    if "/404" in final_url and ("error_code=300031" in final_url or "当前笔记暂时无法浏览" in response_text):
        raise AppError(
            message="这条小红书笔记当前无法公开浏览，系统暂时不能直接编译入库。",
            status_code=403,
            error_code="http_forbidden",
        )
    return response_text


def _strip_html(text: str) -> str:
    collapsed = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    collapsed = re.sub(r"<style[\s\S]*?</style>", " ", collapsed, flags=re.IGNORECASE)
    collapsed = re.sub(r"<[^>]+>", " ", collapsed)
    collapsed = unescape(collapsed)
    collapsed = re.sub(r"\s+", " ", collapsed)
    return normalize_model_output(collapsed).strip()


def _decode_possible_escapes(text: str) -> str:
    normalized = text.strip()
    if "\\u" in normalized or "\\x" in normalized:
        try:
            normalized = bytes(normalized, "utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            pass
    return normalize_model_output(unescape(normalized)).strip()


def _extract_meta_content(html: str, key: str, *, attr: str = "name") -> str | None:
    patterns = [
        rf'<meta[^>]+{attr}="{re.escape(key)}"[^>]+content="([^"]+)"',
        rf"<meta[^>]+{attr}='{re.escape(key)}'[^>]+content='([^']+)'",
        rf'<meta[^>]+content="([^"]+)"[^>]+{attr}="{re.escape(key)}"',
        rf"<meta[^>]+content='([^']+)'[^>]+{attr}='{re.escape(key)}'",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            value = _decode_possible_escapes(match.group(1))
            if value:
                return value
    return None


def _extract_json_candidates(html: str) -> list[dict]:
    candidates: list[dict] = []
    patterns = [
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)</script>',
        r'<script[^>]*type="application/ld\+json"[^>]*>([\s\S]*?)</script>',
        r"window\.__INITIAL_STATE__\s*=\s*({[\s\S]*?})\s*</script>",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE):
            raw_payload = match.group(1).strip()
            try:
                parsed = json.loads(raw_payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                candidates.append(parsed)
    return candidates


def _extract_script_text_candidates(html: str) -> list[str]:
    candidates: list[str] = []
    script_bodies = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html, flags=re.IGNORECASE)
    patterns = [
        r'"desc"\s*:\s*"((?:\\.|[^"\\]){20,})"',
        r'"content"\s*:\s*"((?:\\.|[^"\\]){20,})"',
        r'"articleBody"\s*:\s*"((?:\\.|[^"\\]){20,})"',
        r'"noteDesc"\s*:\s*"((?:\\.|[^"\\]){20,})"',
    ]
    for body in script_bodies:
        for pattern in patterns:
            for match in re.finditer(pattern, body):
                value = _decode_possible_escapes(match.group(1))
                if value:
                    candidates.append(value)
    return candidates


def _looks_like_interview_text(text: str) -> bool:
    normalized = normalize_model_output(text).lower()
    signals = ["面试", "面经", "一面", "二面", "三面", "hr面", "hr 面", "笔试", "反问", "offer"]
    return any(signal in normalized for signal in signals)


def _score_text_candidate(text: str) -> tuple[int, int]:
    normalized = normalize_model_output(text)
    score = 0
    if _looks_like_interview_text(normalized):
        score += 6
    if any(keyword in normalized for keyword in ["产品经理", "算法", "前端", "后端", "运营", "设计", "测试", "数据"]):
        score += 2
    if any(keyword in normalized for keyword in ["问题", "反问", "自我介绍", "项目", "薪资", "offer"]):
        score += 2
    if "小红书" in normalized and len(normalized) < 20:
        score -= 2
    return score, len(normalized)


def _pick_best_text_candidate(candidates: list[str]) -> str | None:
    unique_candidates: list[str] = []
    for candidate in candidates:
        normalized = normalize_model_output(candidate).strip()
        if len(normalized) < 12:
            continue
        if normalized not in unique_candidates:
            unique_candidates.append(normalized)
    if not unique_candidates:
        return None
    unique_candidates.sort(key=_score_text_candidate, reverse=True)
    best = unique_candidates[0]
    if _score_text_candidate(best)[0] <= 0:
        return None
    return best


def _search_nested_payload(data: object) -> dict[str, str | None]:
    if isinstance(data, dict):
        title = None
        content = None
        author_name = None
        published_at = None
        for key, value in data.items():
            key_lower = str(key).lower()
            if title is None and key_lower in {"title", "headline", "note_title", "sharetitle", "displaytitle"} and isinstance(value, str):
                title = value
            if content is None and key_lower in {"desc", "description", "content", "articlebody", "detaildesc", "notecontent", "note_desc", "text"} and isinstance(value, str):
                content = value
            if author_name is None and key_lower in {"author", "nickname", "authorname", "usernickname", "nickName".lower()}:
                if isinstance(value, str):
                    author_name = value
                elif isinstance(value, dict):
                    nested_author = value.get("name") or value.get("nickname")
                    if isinstance(nested_author, str):
                        author_name = nested_author
            if published_at is None and key_lower in {"datepublished", "publishedat", "publish_time", "time", "lastupdate", "uploadtime"} and isinstance(value, str):
                published_at = value
            if any(item is None for item in [title, content, author_name, published_at]):
                nested = _search_nested_payload(value)
                title = title or nested.get("title")
                content = content or nested.get("content_raw")
                author_name = author_name or nested.get("author_name")
                published_at = published_at or nested.get("published_at")
        return {
            "title": normalize_model_output(title or "").strip() or None,
            "content_raw": normalize_model_output(content or "").strip() or None,
            "author_name": normalize_model_output(author_name or "").strip() or None,
            "published_at": normalize_model_output(published_at or "").strip() or None,
        }
    if isinstance(data, list):
        for item in data:
            nested = _search_nested_payload(item)
            if nested.get("content_raw"):
                return nested
    return {"title": None, "content_raw": None, "author_name": None, "published_at": None}


def extract_note_payload(html: str, url: str) -> dict[str, str | None]:
    title: str | None = None
    content_raw: str | None = None
    author_name: str | None = None
    published_at: str | None = None

    for candidate in _extract_json_candidates(html):
        payload = _search_nested_payload(candidate)
        title = title or payload.get("title")
        content_raw = content_raw or payload.get("content_raw")
        author_name = author_name or payload.get("author_name")
        published_at = published_at or payload.get("published_at")

    if title is None:
        title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            title = normalize_model_output(_strip_html(title_match.group(1))) or None

    if title is None:
        title = (
            _extract_meta_content(html, "og:title", attr="property")
            or _extract_meta_content(html, "twitter:title", attr="name")
            or _extract_meta_content(html, "title", attr="name")
        )

    if content_raw is None:
        content_raw = (
            _extract_meta_content(html, "description", attr="name")
            or _extract_meta_content(html, "og:description", attr="property")
            or _extract_meta_content(html, "twitter:description", attr="name")
        )

    if content_raw is None:
        content_raw = _pick_best_text_candidate(_extract_script_text_candidates(html))

    if content_raw is None:
        body_match = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, flags=re.IGNORECASE)
        if body_match:
            body_html = body_match.group(1)
            fallback_text = _strip_html(body_html)
            fallback_candidate = _pick_best_text_candidate(
                re.split(r"[。！？\n]|</p>|<br\s*/?>", body_html, flags=re.IGNORECASE) + [fallback_text]
            )
            if fallback_candidate:
                fallback_text = fallback_candidate
            content_raw = fallback_text[:4000] or None

    if content_raw and title and not _looks_like_interview_text(content_raw) and _looks_like_interview_text(title):
        content_raw = f"{title}\n{content_raw}"

    if not content_raw:
        raise AppError(
            message="未能从小红书公开页提取到正文。",
            status_code=422,
            error_code="content_unavailable",
        )

    return {
        "url": _normalize_url(url),
        "title": title,
        "content_raw": content_raw,
        "author_name": author_name,
        "published_at": published_at,
    }


def compile_note_to_import_item(
    payload: dict[str, str | None],
    *,
    default_company: str | None = None,
    default_role: str | None = None,
    default_city: str | None = None,
) -> InterviewKnowledgeImportItem:
    item = InterviewKnowledgeImportItem(
        source_id=urlparse(payload["url"] or "").path.strip("/").replace("/", "-") or None,
        url=payload["url"],
        title=payload.get("title"),
        author_name=payload.get("author_name"),
        published_at=payload.get("published_at"),
        company=default_company,
        role=default_role,
        city=default_city,
        content_raw=payload.get("content_raw") or "",
    )
    clean_content = _build_clean_content(item)
    if not clean_content:
        raise AppError(
            message="提取到的正文为空，无法编译。",
            status_code=422,
            error_code="content_unavailable",
        )
    if not _is_valid_interview_experience(clean_content, item.title):
        raise AppError(
            message="当前链接内容不像有效面试经验，已跳过。",
            status_code=422,
            error_code="not_interview_experience",
        )

    item.company = item.company or _infer_company(item, clean_content)
    item.role = item.role or _infer_role(item, clean_content)
    item.interview_stage = _infer_interview_stage(clean_content, item.interview_stage)
    item.content_summary = _build_summary(clean_content, None)
    return item


def compile_xiaohongshu_links(
    db: Session,
    links: list[str],
    *,
    default_company: str | None = None,
    default_role: str | None = None,
    default_city: str | None = None,
    compliance_status: str | None = None,
) -> InterviewKnowledgeCompileLinksResponse:
    compiled_items: list[InterviewKnowledgeImportItem] = []
    results: list[InterviewKnowledgeCompileResult] = []

    for raw_url in links:
        normalized_url = _normalize_url(raw_url)
        try:
            normalized_url = _validate_xiaohongshu_url(normalized_url)
            html = fetch_public_page(normalized_url)
            payload = extract_note_payload(html, normalized_url)
            item = compile_note_to_import_item(
                payload,
                default_company=default_company,
                default_role=default_role,
                default_city=default_city,
            )
            compiled_items.append(item)
            results.append(
                InterviewKnowledgeCompileResult(
                    url=normalized_url,
                    status="compiled",
                    source_id=item.source_id,
                    title=item.title,
                    company=item.company,
                    role=item.role,
                    interview_stage=item.interview_stage,
                    city=item.city,
                    content_summary=item.content_summary,
                )
            )
        except AppError as exc:
            results.append(
                InterviewKnowledgeCompileResult(
                    url=normalized_url,
                    status="failed",
                    error=exc.error_code,
                )
            )
        except Exception:
            results.append(
                InterviewKnowledgeCompileResult(
                    url=normalized_url,
                    status="failed",
                    error="parse_failed",
                )
            )

    imported_count = 0
    if compiled_items:
        try:
            import_response = import_xiaohongshu_research_knowledge(db, compiled_items)
            imported_by_url = {source.url or "": source for source in import_response.sources}
            imported_count = import_response.imported_count
            for index, result in enumerate(results):
                if result.status != "compiled":
                    continue
                source = imported_by_url.get(result.url)
                if source is None:
                    results[index] = InterviewKnowledgeCompileResult(
                        url=result.url,
                        status="failed",
                        error="import_failed",
                        source_id=result.source_id,
                        title=result.title,
                        company=result.company,
                        role=result.role,
                        interview_stage=result.interview_stage,
                        city=result.city,
                        content_summary=result.content_summary,
                    )
                else:
                    results[index] = InterviewKnowledgeCompileResult(
                        url=result.url,
                        status="imported",
                        source_id=source.source_id,
                        title=source.title,
                        company=source.company,
                        role=source.role,
                        interview_stage=source.interview_stage,
                        city=source.city,
                        content_summary=source.content_summary,
                    )
        except AppError:
            for index, result in enumerate(results):
                if result.status == "compiled":
                    results[index] = InterviewKnowledgeCompileResult(
                        url=result.url,
                        status="failed",
                        error="import_failed",
                        source_id=result.source_id,
                        title=result.title,
                        company=result.company,
                        role=result.role,
                        interview_stage=result.interview_stage,
                        city=result.city,
                        content_summary=result.content_summary,
                    )

    return InterviewKnowledgeCompileLinksResponse(
        requested_count=len(links),
        compiled_count=len(compiled_items),
        imported_count=imported_count,
        failed_count=sum(1 for result in results if result.status == "failed"),
        results=results,
    )
