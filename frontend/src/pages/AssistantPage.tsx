import { Fragment, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { getAssistantThread, streamAssistantChat } from "../features/jobs/api";
import { useJobs } from "../features/jobs/hooks";
import type { AssistantMessage, AssistantThreadResponse } from "../features/jobs/types";
import { ApiError } from "../shared/api/client";
import { Button } from "../shared/ui/Button";
import { Card } from "../shared/ui/Card";
import { EmptyState } from "../shared/ui/EmptyState";
import { Field } from "../shared/ui/Field";
import { StatusPill } from "../shared/ui/StatusPill";

const STORAGE_KEY = "findgoodjob.selected.job.id";

const SUGGESTED_PROMPTS = [
  "根据当前岗位，先告诉我简历最该补的 3 个点",
  "帮我总结这个岗位最看重的能力和关键词",
  "如果我要投这个岗位，接下来 3 步应该做什么",
  "请用更像 HR 读起来顺的方式优化我的自我介绍",
];

function loadSelectedJobId() {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw ? Number(raw) : null;
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "求职助手暂时不可用，请稍后再试。";
}

function buildOptimisticAssistantMessage(): AssistantMessage {
  return {
    id: -Date.now(),
    role: "assistant",
    content: "",
    sequence: Number.MAX_SAFE_INTEGER,
    created_at: null,
    retrieval_note: null,
    source_links: [],
  };
}

function renderMessageContent(content: string) {
  const parts = content.split(/(https?:\/\/[^\s]+)/g);
  return parts.map((part, index) => {
    if (/^https?:\/\/[^\s]+$/.test(part)) {
      return (
        <a
          key={`${part}-${index}`}
          href={part}
          target="_blank"
          rel="noreferrer"
          className="assistant-inline-link"
        >
          {part}
        </a>
      );
    }
    return <Fragment key={`text-${index}`}>{part}</Fragment>;
  });
}

export function AssistantPage() {
  const jobsQuery = useJobs();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(() => loadSelectedJobId());
  const [thread, setThread] = useState<AssistantThreadResponse | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [threadError, setThreadError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const threadRef = useRef<HTMLDivElement | null>(null);

  const jobs = jobsQuery.data ?? [];
  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? null,
    [jobs, selectedJobId],
  );

  useEffect(() => {
    if (jobs.length > 0 && selectedJobId === null) {
      const nextJobId = jobs[0].id;
      setSelectedJobId(nextJobId);
      window.localStorage.setItem(STORAGE_KEY, String(nextJobId));
    }
  }, [jobs, selectedJobId]);

  useEffect(() => {
    if (selectedJobId === null) {
      setThread(null);
      setThreadError(null);
      return;
    }

    let cancelled = false;
    const jobId = selectedJobId;

    async function loadThread() {
      setThreadLoading(true);
      setThreadError(null);
      try {
        const data = await getAssistantThread(jobId);
        if (!cancelled) {
          setThread(data);
        }
      } catch (error) {
        if (!cancelled) {
          setThread(null);
          setThreadError(getErrorMessage(error));
        }
      } finally {
        if (!cancelled) {
          setThreadLoading(false);
        }
      }
    }

    void loadThread();

    return () => {
      cancelled = true;
    };
  }, [selectedJobId]);

  useEffect(() => {
    if (!threadRef.current) {
      return;
    }
    threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [thread?.messages, sending]);

  async function handleSendMessage(messageText: string) {
    const trimmed = messageText.trim();
    if (!trimmed || sending || selectedJobId === null || !thread?.can_chat) {
      return;
    }

    const optimisticUserMessage: AssistantMessage = {
      id: -Date.now(),
      role: "user",
      content: trimmed,
      sequence: ((thread.messages[thread.messages.length - 1]?.sequence ?? 0) + 1),
      created_at: null,
    };
    const optimisticAssistantMessage = buildOptimisticAssistantMessage();

    setThreadError(null);
    setInput("");
    setSending(true);
    setThread((current) =>
      current
        ? {
            ...current,
            messages: [...current.messages, optimisticUserMessage, optimisticAssistantMessage],
          }
        : current,
    );

    try {
      const result = await streamAssistantChat(selectedJobId, { message: trimmed }, (content) => {
        setThread((current) => {
          if (!current) {
            return current;
          }
          const messages = [...current.messages];
          const lastIndex = messages.length - 1;
          if (lastIndex >= 0) {
            messages[lastIndex] = {
              ...messages[lastIndex],
              content,
            };
          }
          return { ...current, messages };
        });
      });

      setThread((current) => {
        if (!current) {
          return current;
        }
        const messages = current.messages.slice(0, -1).concat(result.message);
        return {
          ...current,
          summary_text: result.summary_text,
          workspace_summary: result.workspace_summary,
          messages,
        };
      });
    } catch (error) {
      setThreadError(getErrorMessage(error));
      setThread((current) =>
        current
          ? {
              ...current,
              messages: current.messages.slice(0, -2),
            }
          : current,
      );
      setInput(trimmed);
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void handleSendMessage(input);
  }

  const emptyThread = !threadLoading && thread && thread.messages.length === 0;

  return (
    <div className="app-shell assistant-page-shell">
      <header className="assistant-page-header">
        <div>
          <div className="assistant-page-kicker">FindGoodJob Assistant</div>
          <h1 className="app-title">AI 求职助手</h1>
          <p className="app-subtitle">把岗位理解、简历优化、投递准备和面试问题放进一个连续对话里推进。</p>
        </div>
        <div className="assistant-page-header-actions">
          <Link to="/knowledge-base" className="btn btn-ghost btn-pill assistant-back-link">
            知识库管理
          </Link>
          <StatusPill tone={thread?.can_chat ? "success" : "warning"}>
            {thread?.can_chat ? "DeepSeek 已连接" : "助手未配置"}
          </StatusPill>
          <Link to="/" className="btn btn-ghost btn-pill assistant-back-link">
            返回工作台
          </Link>
        </div>
      </header>

      {threadError ? <div className="error-banner">{threadError}</div> : null}

      <div className="assistant-page-grid">
        <div className="assistant-page-main">
          <Card
            title="对话工作区"
            subtitle={
              selectedJob
                ? `当前记忆归属岗位：${selectedJob.title} @ ${selectedJob.company}`
                : "先在右侧选择一个岗位，再开始对话。"
            }
            className="assistant-chat-card"
          >
            <div ref={threadRef} className="assistant-chat-thread">
              {threadLoading ? <div className="content-box">正在加载该岗位的助手记忆...</div> : null}

              {emptyThread ? (
                <article className="assistant-chat-bubble assistant-chat-bubble-assistant">
                  <div className="assistant-chat-role">AI 助手</div>
                  <div className="assistant-chat-content">
                    我已经拿到当前岗位工作台摘要，可以继续帮你做岗位理解、简历优化、投递准备和面试问题梳理。直接开始问就行。
                  </div>
                </article>
              ) : null}

              {thread?.messages.map((message) => (
                <article key={message.id} className={`assistant-chat-bubble assistant-chat-bubble-${message.role}`}>
                  <div className="assistant-chat-role">{message.role === "assistant" ? "AI 助手" : "你"}</div>
                  {message.role === "assistant" && !message.content ? (
                    <div className="assistant-chat-typing">
                      <span />
                      <span />
                      <span />
                    </div>
                  ) : (
                    <>
                      {message.role === "assistant" && message.retrieval_note ? (
                        <div className="assistant-retrieval-strip">{message.retrieval_note}</div>
                      ) : null}
                      <div className="assistant-chat-content">{renderMessageContent(message.content)}</div>
                      {message.role === "assistant" && (message.source_links?.length ?? 0) > 0 ? (
                        <div className="assistant-source-links">
                          <div className="assistant-source-links-label">参考来源</div>
                          <div className="assistant-source-links-list">
                            {message.source_links?.map((link) => (
                              <a
                                key={link}
                                href={link}
                                target="_blank"
                                rel="noreferrer"
                                className="assistant-inline-link"
                              >
                                {link}
                              </a>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </>
                  )}
                </article>
              ))}
            </div>

            <div className="assistant-suggestion-row">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="assistant-suggestion-chip"
                  onClick={() => void handleSendMessage(prompt)}
                  disabled={sending || !thread?.can_chat || selectedJobId === null}
                >
                  {prompt}
                </button>
              ))}
            </div>

            <form className="assistant-composer" onSubmit={handleSubmit}>
              <Field label="输入你的问题" hint="当前页会自动记住该岗位下的全部对话">
                <textarea
                  className="text-area assistant-composer-input"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="例如：这是我的一段项目经历，帮我改成更适合这个岗位投递的表达。"
                  disabled={selectedJobId === null}
                />
              </Field>
              <div className="assistant-composer-actions">
                <div className="assistant-composer-hint">
                  {thread?.can_chat
                    ? "回复会以流式方式返回，并自动写入该岗位的混合记忆。"
                    : "未配置 DEEPSEEK_API_KEY 时，只能查看历史记忆，暂时不能发送新问题。"}
                </div>
                <Button
                  className="btn-hero"
                  type="submit"
                  disabled={!input.trim() || sending || selectedJobId === null || !thread?.can_chat}
                >
                  {sending ? "思考中..." : "发送给 AI 助手"}
                </Button>
              </div>
            </form>
          </Card>
        </div>

        <div className="assistant-page-side">
          <Card title="岗位上下文" subtitle="切换岗位时，会切换到该岗位自己的记忆。">
            {jobsQuery.isLoading ? (
              <div className="content-box">正在读取岗位列表...</div>
            ) : jobs.length === 0 ? (
              <EmptyState
                title="还没有岗位"
                description="先回到工作台创建岗位，聊天页才能带着岗位工作台信息和混合记忆工作。"
                action={
                  <Link to="/" className="btn btn-primary btn-pill assistant-empty-link">
                    去创建岗位
                  </Link>
                }
              />
            ) : (
              <div className="assistant-job-list">
                {jobs.map((job) => (
                  <button
                    key={job.id}
                    type="button"
                    className={`assistant-job-item ${selectedJobId === job.id ? "assistant-job-item-active" : ""}`.trim()}
                    onClick={() => {
                      setSelectedJobId(job.id);
                      window.localStorage.setItem(STORAGE_KEY, String(job.id));
                    }}
                  >
                    <div className="assistant-job-item-top">
                      <strong>{job.title}</strong>
                      <StatusPill tone={job.analysis_result ? "success" : "warning"}>
                        {job.analysis_result ? "已分析" : "待分析"}
                      </StatusPill>
                    </div>
                    <div className="assistant-job-item-company">{job.company}</div>
                  </button>
                ))}
              </div>
            )}
          </Card>

          <Card title="工作台摘要" subtitle="助手会把这些稳定信息持续带入对话。">
            <div className="content-box assistant-summary-box">
              {thread?.workspace_summary ?? "请选择岗位后查看工作台摘要。"}
            </div>
          </Card>

          <Card title="记忆摘要" subtitle="这是该岗位自动压缩出来的历史记忆。">
            <div className="content-box assistant-summary-box">
              {thread?.summary_text ?? "暂无对话记忆。"}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
