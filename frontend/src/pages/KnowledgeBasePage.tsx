import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  compileXiaohongshuLinks,
  getInterviewKnowledgeSources,
  importManualKnowledge,
  importResearchKnowledge,
  reindexInterviewKnowledge,
  searchInterviewKnowledge,
} from "../features/jobs/api";
import type {
  InterviewKnowledgeCompileLinksResponse,
  InterviewKnowledgeImportRequest,
  InterviewKnowledgeImportResponse,
  InterviewKnowledgeReindexResponse,
  InterviewKnowledgeSearchResponse,
  InterviewKnowledgeSourceListResponse,
} from "../features/jobs/types";
import { ApiError } from "../shared/api/client";
import { Button } from "../shared/ui/Button";
import { Card } from "../shared/ui/Card";
import { Field } from "../shared/ui/Field";
import { StatusPill } from "../shared/ui/StatusPill";

const DEFAULT_MANUAL_JSON = JSON.stringify(
  {
    items: [
      {
        source_id: "note-001",
        url: "https://www.xiaohongshu.com/explore/note-001",
        title: "美团产品经理一面面经",
        author_name: "候选人A",
        published_at: "2026-04-10T10:00:00+08:00",
        company: "美团",
        role: "产品经理",
        interview_stage: "一面",
        city: "北京",
        tags: ["产品经理", "面经", "校招"],
        quality_score: 85,
        content_raw: "美团产品经理一面主要问了用户增长、需求拆解、竞品分析，还会要求候选人做反问。",
        content_summary: "美团产品经理一面重点考察用户增长、需求拆解和竞品分析。",
        metadata: {
          collector: "manual",
          remark: "人工整理",
        },
      },
    ],
  },
  null,
  2,
);

const DEFAULT_RESEARCH_JSON = JSON.stringify(
  {
    items: [
      {
        source_id: "research-note-001",
        url: "https://www.xiaohongshu.com/explore/research-note-001",
        title: "阿里面试复盘",
        author_name: "研究样本A",
        published_at: "2026-04-09T09:00:00+08:00",
        crawl_at: "2026-04-12T15:00:00+08:00",
        company: "阿里",
        role: "产品经理",
        interview_stage: "二面",
        city: "杭州",
        tags: ["阿里", "产品经理", "二面"],
        quality_score: 78,
        content_raw: "阿里产品经理二面更关注业务理解、数据分析和项目推进，追问会比较深入。",
        content_summary: "阿里产品经理二面偏业务理解和深入追问。",
        metadata: {
          collector: "research",
          remark: "公开页研究样本",
        },
      },
    ],
  },
  null,
  2,
);

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "知识库操作失败，请稍后重试。";
}

function parseJsonPayload<T>(raw: string): T {
  return JSON.parse(raw) as T;
}

function buildManualFallbackJsonFromCompileResult(response: InterviewKnowledgeCompileLinksResponse) {
  const items = response.results
    .filter(
      (result) =>
        result.status === "failed" &&
        ["http_forbidden", "content_unavailable", "fetch_failed", "http_not_found"].includes(result.error ?? ""),
    )
    .map((result, index) => ({
      source_id: result.source_id || `manual-fallback-${Date.now()}-${index + 1}`,
      url: result.url,
      title: result.title || "",
      author_name: "",
      published_at: "",
      company: result.company || "",
      role: result.role || "",
      interview_stage: result.interview_stage || "",
      city: result.city || "",
      tags: result.role ? [result.role, "面经"] : ["面经"],
      quality_score: 75,
      content_raw: "请把这条链接对应的正文摘要粘贴到这里，再点击“写入手工面经”。",
      content_summary: result.content_summary || "请补充 1 到 2 句的面经摘要。",
      metadata: {
        collector: "manual_fallback",
        remark: "链接不可公开抓取后转手工补录",
        original_error: result.error,
      },
    }));

  if (items.length === 0) {
    return null;
  }

  return JSON.stringify({ items }, null, 2);
}

function formatTime(value: string | null) {
  if (!value) {
    return "未知";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function KnowledgeBasePage() {
  const [manualJson, setManualJson] = useState(DEFAULT_MANUAL_JSON);
  const [researchJson, setResearchJson] = useState(DEFAULT_RESEARCH_JSON);
  const [linkInput, setLinkInput] = useState(
    "https://www.xiaohongshu.com/explore/note-001\nhttps://www.xiaohongshu.com/explore/note-002",
  );
  const [defaultCompany, setDefaultCompany] = useState("美团");
  const [defaultRole, setDefaultRole] = useState("产品经理");
  const [defaultCity, setDefaultCity] = useState("北京");
  const [searchQuery, setSearchQuery] = useState("美团产品经理一面问什么");
  const [searchCompany, setSearchCompany] = useState("美团");
  const [searchRole, setSearchRole] = useState("产品经理");
  const [searchStage, setSearchStage] = useState("");
  const [searchCity, setSearchCity] = useState("");
  const [busyAction, setBusyAction] = useState<"manual" | "research" | "compile" | "search" | "reindex" | null>(
    null,
  );
  const [banner, setBanner] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [manualFallbackNotice, setManualFallbackNotice] = useState<string | null>(null);
  const [lastImportResult, setLastImportResult] = useState<InterviewKnowledgeImportResponse | null>(null);
  const [lastCompileResult, setLastCompileResult] = useState<InterviewKnowledgeCompileLinksResponse | null>(null);
  const [lastReindexResult, setLastReindexResult] = useState<InterviewKnowledgeReindexResponse | null>(null);
  const [searchResult, setSearchResult] = useState<InterviewKnowledgeSearchResponse | null>(null);
  const [sourceList, setSourceList] = useState<InterviewKnowledgeSourceListResponse | null>(null);
  const [sourceListLoading, setSourceListLoading] = useState(false);

  const knowledgeSummary = useMemo(() => {
    const importCount = lastImportResult?.imported_count ?? 0;
    const compileCount = lastCompileResult?.imported_count ?? 0;
    const storedCount = sourceList?.total_count ?? 0;
    return [
      { label: "最近导入", value: String(importCount) },
      { label: "最近编译入库", value: String(compileCount) },
      { label: "已入库知识数", value: String(storedCount) },
    ];
  }, [lastCompileResult, lastImportResult, sourceList]);

  async function loadSourceList() {
    setSourceListLoading(true);
    try {
      const response = await getInterviewKnowledgeSources(50);
      setSourceList(response);
    } finally {
      setSourceListLoading(false);
    }
  }

  useEffect(() => {
    void loadSourceList().catch((error) => {
      setBanner({ tone: "error", text: getErrorMessage(error) });
    });
  }, []);

  async function handleManualImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("manual");
    setBanner(null);
    setManualFallbackNotice(null);
    try {
      const payload = parseJsonPayload<InterviewKnowledgeImportRequest>(manualJson);
      const response = await importManualKnowledge(payload);
      setLastImportResult(response);
      await loadSourceList();
      setBanner({ tone: "success", text: `手工导入完成，已写入 ${response.imported_count} 条记录。` });
    } catch (error) {
      setBanner({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }

  async function handleResearchImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("research");
    setBanner(null);
    setManualFallbackNotice(null);
    try {
      const payload = parseJsonPayload<InterviewKnowledgeImportRequest>(researchJson);
      const response = await importResearchKnowledge(payload);
      setLastImportResult(response);
      await loadSourceList();
      setBanner({ tone: "success", text: `研究数据导入完成，已写入 ${response.imported_count} 条记录。` });
    } catch (error) {
      setBanner({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCompileLinks(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("compile");
    setBanner(null);
    setManualFallbackNotice(null);
    try {
      const links = linkInput
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean);
      const response = await compileXiaohongshuLinks({
        links,
        default_company: defaultCompany || undefined,
        default_role: defaultRole || undefined,
        default_city: defaultCity || undefined,
      });
      setLastCompileResult(response);
      await loadSourceList();
      const fallbackJson = buildManualFallbackJsonFromCompileResult(response);
      if (fallbackJson) {
        setManualJson(fallbackJson);
        setManualFallbackNotice(
          "有些链接当前不能公开抓取，系统已经为你生成手工补录模板。把正文摘要粘贴进上方“手工导入 JSON”的 content_raw 和 content_summary 后，直接点击“写入手工面经”即可继续入库。",
        );
      }
      setBanner({
        tone: response.failed_count > 0 ? "error" : "success",
        text:
          response.failed_count > 0
            ? `链接编译完成，成功入库 ${response.imported_count} 条，失败 ${response.failed_count} 条。`
            : `链接编译完成，已成功入库 ${response.imported_count} 条。`,
      });
    } catch (error) {
      setBanner({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("search");
    setBanner(null);
    try {
      const response = await searchInterviewKnowledge({
        query: searchQuery,
        company: searchCompany || undefined,
        role: searchRole || undefined,
        interview_stage: searchStage || undefined,
        city: searchCity || undefined,
        top_k: 6,
      });
      setSearchResult(response);
      setBanner({ tone: "success", text: `搜索完成，返回 ${response.result_count} 条结果。` });
    } catch (error) {
      setBanner({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }

  async function handleReindex() {
    setBusyAction("reindex");
    setBanner(null);
    try {
      const response = await reindexInterviewKnowledge();
      setLastReindexResult(response);
      await loadSourceList();
      setBanner({
        tone: "success",
        text: `向量重建完成，已更新 ${response.source_count} 条来源、${response.chunk_count} 个切片。`,
      });
    } catch (error) {
      setBanner({ tone: "error", text: getErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <div className="app-shell knowledge-page-shell">
      <header className="assistant-page-header">
        <div>
          <div className="assistant-page-kicker">FindGoodJob Knowledge</div>
          <h1 className="app-title">知识库管理</h1>
          <p className="app-subtitle">
            在这里统一做面经导入、链接自动编译和知识检索验证。导入成功后，求职助手会自动复用这些知识片段做 RAG 检索。
          </p>
        </div>
        <div className="assistant-page-header-actions">
          <StatusPill tone="success">面经知识库</StatusPill>
          <button
            type="button"
            className="btn btn-ghost btn-pill assistant-back-link"
            onClick={() => void handleReindex()}
            disabled={busyAction !== null}
          >
            {busyAction === "reindex" ? "重建中..." : "重建向量索引"}
          </button>
          <Link to="/assistant" className="btn btn-ghost btn-pill assistant-back-link">
            返回 AI 求职助手
          </Link>
        </div>
      </header>

      {banner ? <div className={banner.tone === "success" ? "success-banner" : "error-banner"}>{banner.text}</div> : null}
      {manualFallbackNotice ? <div className="knowledge-fallback-banner">{manualFallbackNotice}</div> : null}

      <div className="knowledge-hero-grid">
        {knowledgeSummary.map((item) => (
          <Card key={item.label} className="knowledge-stat-card">
            <div className="knowledge-stat-label">{item.label}</div>
            <div className="knowledge-stat-value">{item.value}</div>
          </Card>
        ))}
      </div>

      <div className="knowledge-page-grid">
        <div className="knowledge-page-main">
          <Card
            title="手工导入"
            subtitle="适合人工整理或授权面经。直接编辑 JSON 后提交。"
            className="knowledge-card"
          >
            <form className="stack" onSubmit={handleManualImport}>
              <Field label="手工导入 JSON" hint="字段结构与 docs 里的 sample payload 保持一致。">
                <textarea
                  className="text-area text-area-xl knowledge-json-area"
                  value={manualJson}
                  onChange={(event) => setManualJson(event.target.value)}
                />
              </Field>
              <div className="panel-actions">
                <Button className="btn-pill" type="submit" disabled={busyAction !== null}>
                  {busyAction === "manual" ? "导入中..." : "写入手工面经"}
                </Button>
              </div>
            </form>
          </Card>

          <Card title="研究导入" subtitle="适合已经采集完成的公开研究样本。" className="knowledge-card">
            <form className="stack" onSubmit={handleResearchImport}>
              <Field label="研究导入 JSON" hint="会按 public_research 标记写入。">
                <textarea
                  className="text-area text-area-xl knowledge-json-area"
                  value={researchJson}
                  onChange={(event) => setResearchJson(event.target.value)}
                />
              </Field>
              <div className="panel-actions">
                <Button className="btn-pill" type="submit" disabled={busyAction !== null}>
                  {busyAction === "research" ? "导入中..." : "写入研究样本"}
                </Button>
              </div>
            </form>
          </Card>

          <Card
            title="链接自动编译"
            subtitle="只给小红书公开链接，系统会尝试抓取、抽正文、摘要并入库。"
            className="knowledge-card"
          >
            <form className="stack" onSubmit={handleCompileLinks}>
              <Field label="小红书公开链接" hint="一行一个链接。">
                <textarea
                  className="text-area knowledge-link-area"
                  value={linkInput}
                  onChange={(event) => setLinkInput(event.target.value)}
                />
              </Field>
              <div className="split-fields">
                <Field label="默认公司">
                  <input
                    className="text-input"
                    value={defaultCompany}
                    onChange={(event) => setDefaultCompany(event.target.value)}
                    placeholder="例如：美团"
                  />
                </Field>
                <Field label="默认岗位">
                  <input
                    className="text-input"
                    value={defaultRole}
                    onChange={(event) => setDefaultRole(event.target.value)}
                    placeholder="例如：产品经理"
                  />
                </Field>
              </div>
              <Field label="默认城市">
                <input
                  className="text-input"
                  value={defaultCity}
                  onChange={(event) => setDefaultCity(event.target.value)}
                  placeholder="例如：北京"
                />
              </Field>
              <div className="panel-actions">
                <Button className="btn-pill" type="submit" disabled={busyAction !== null}>
                  {busyAction === "compile" ? "编译中..." : "编译链接并入库"}
                </Button>
              </div>
            </form>
          </Card>
        </div>

        <div className="knowledge-page-side">
          <Card title="已入库知识" subtitle="这里展示真实持久化到数据库中的知识来源，刷新页面后仍会重新读取。">
            {sourceListLoading ? (
              <div className="content-box">正在读取已入库知识...</div>
            ) : sourceList && sourceList.sources.length > 0 ? (
              <div className="knowledge-import-result-list">
                {sourceList.sources.map((source) => (
                  <article key={source.id} className="knowledge-result-card">
                    <div className="assistant-job-item-top">
                      <strong>{source.title || "未命名面经"}</strong>
                      <StatusPill tone={source.embedding_ready ? "success" : "warning"}>
                        {source.embedding_ready ? "已向量化" : "待重建"}
                      </StatusPill>
                    </div>
                    <div className="knowledge-result-meta">
                      {(source.company || "未知公司") + " 路 " + (source.role || "未知岗位")} 路 {source.interview_stage || "未知轮次"}
                    </div>
                    <div className="knowledge-result-summary">{source.content_summary}</div>
                    <div className="knowledge-result-meta">
                      {`切片 ${source.chunk_count} 个 · ${source.compliance_status} · 更新时间 ${formatTime(source.updated_at || source.ingest_at)}`}
                    </div>
                    {source.url ? (
                      <a href={source.url} target="_blank" rel="noreferrer" className="assistant-inline-link">
                        {source.url}
                      </a>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <div className="content-box">还没有已入库知识。先导入一条面经后，这里会稳定显示真实持久化结果。</div>
            )}
          </Card>

          <Card title="搜索验证" subtitle="导入后立刻在这里做知识检索，确认能否被助手召回。">
            <form className="stack" onSubmit={handleSearch}>
              <Field label="搜索问题">
                <input className="text-input" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} />
              </Field>
              <div className="split-fields">
                <Field label="公司">
                  <input
                    className="text-input"
                    value={searchCompany}
                    onChange={(event) => setSearchCompany(event.target.value)}
                    placeholder="可选"
                  />
                </Field>
                <Field label="岗位">
                  <input
                    className="text-input"
                    value={searchRole}
                    onChange={(event) => setSearchRole(event.target.value)}
                    placeholder="可选"
                  />
                </Field>
              </div>
              <div className="split-fields">
                <Field label="轮次">
                  <input
                    className="text-input"
                    value={searchStage}
                    onChange={(event) => setSearchStage(event.target.value)}
                    placeholder="例如：一面"
                  />
                </Field>
                <Field label="城市">
                  <input
                    className="text-input"
                    value={searchCity}
                    onChange={(event) => setSearchCity(event.target.value)}
                    placeholder="可选"
                  />
                </Field>
              </div>
              <div className="panel-actions">
                <Button className="btn-pill" type="submit" disabled={busyAction !== null}>
                  {busyAction === "search" ? "搜索中..." : "搜索知识库"}
                </Button>
              </div>
            </form>
          </Card>

          <Card title="最近导入结果" subtitle="手工导入或研究导入成功后，会在这里显示即时回执。">
            {lastImportResult ? (
              <div className="knowledge-import-result-list">
                {lastImportResult.sources.map((source) => (
                  <article key={source.id} className="knowledge-result-card">
                    <div className="assistant-job-item-top">
                      <strong>{source.title || "未命名面经"}</strong>
                      <StatusPill tone={source.embedding_ready ? "success" : "warning"}>
                        {source.embedding_ready ? "已向量化" : "待重建"}
                      </StatusPill>
                    </div>
                    <div className="knowledge-result-meta">
                      {(source.company || "未知公司") + " 路 " + (source.role || "未知岗位")}
                    </div>
                    <div className="knowledge-result-summary">{source.content_summary}</div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="content-box">还没有新的导入回执。你可以先试一条样例 JSON。</div>
            )}
          </Card>

          {lastReindexResult ? (
            <Card title="最近向量重建" subtitle="最近一次重建索引的执行结果。">
              <div className="content-box">
                {`来源 ${lastReindexResult.source_count} 条，文档 ${lastReindexResult.document_count} 条，切片 ${lastReindexResult.chunk_count} 个。`}
              </div>
            </Card>
          ) : null}

          <Card title="最近链接编译结果" subtitle="这里会显示每条链接是否编译成功，以及失败原因。">
            {lastCompileResult ? (
              <div className="knowledge-import-result-list">
                {lastCompileResult.results.map((result) => (
                  <article key={`${result.url}-${result.status}`} className="knowledge-result-card">
                    <div className="assistant-job-item-top">
                      <strong>{result.title || result.url}</strong>
                      <StatusPill tone={result.status === "imported" ? "success" : "warning"}>
                        {result.status === "imported" ? "已入库" : result.error || result.status}
                      </StatusPill>
                    </div>
                    <div className="knowledge-result-meta">
                      {(result.company || "未知公司") + " 路 " + (result.role || "未知岗位")}
                    </div>
                    <div className="knowledge-result-summary">
                      {result.content_summary || "这条链接没有生成可展示的摘要。"}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="content-box">还没有链接编译结果。你可以先粘贴一条公开链接试试。</div>
            )}
          </Card>

          <Card title="搜索结果预览" subtitle="这里展示当前 query 命中的知识片段，方便做 RAG 联调。">
            {searchResult ? (
              searchResult.results.length > 0 ? (
                <div className="knowledge-import-result-list">
                  {searchResult.results.map((item) => (
                    <article key={`${item.source_record_id}-${item.score}`} className="knowledge-result-card">
                      <div className="assistant-job-item-top">
                        <strong>{item.title || "未命名结果"}</strong>
                        <StatusPill tone="neutral">score {item.score.toFixed(3)}</StatusPill>
                      </div>
                      <div className="knowledge-result-meta">
                        {(item.company || "未知公司") + " 路 " + (item.role || "未知岗位")} 路 {item.interview_stage || "未知轮次"}
                      </div>
                      <div className="knowledge-result-summary">{item.content_summary}</div>
                      <div className="content-box knowledge-chunk-box">{item.chunk_text}</div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="content-box">当前搜索没有命中结果，可以换一个 query 或放宽过滤条件。</div>
              )
            ) : (
              <div className="content-box">还没有搜索结果。导入后可以直接在这里做知识检索验证。</div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
