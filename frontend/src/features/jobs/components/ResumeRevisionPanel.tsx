import { Fragment, type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../../../shared/api/client";
import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Field } from "../../../shared/ui/Field";
import { StatusPill } from "../../../shared/ui/StatusPill";
import { copyText } from "../../../shared/utils/clipboard";
import { useParseResumeDocument } from "../hooks";
import type { JobResponse, ResumeRevisionResponse } from "../types";

type ResumeRevisionPanelProps = {
  job: JobResponse | null;
  revising: boolean;
  streamingContent: string;
  result: ResumeRevisionResponse | null;
  onRevise: (resumeText: string) => Promise<void>;
};

type DiffSegment = {
  text: string;
  changed: boolean;
};

const ACCEPTED_FILE_TYPES = ".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff";

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "文件解析失败，请稍后重试。";
}

function getScoreTone(score: number | null) {
  if (score === null) {
    return "neutral" as const;
  }
  if (score >= 85) {
    return "success" as const;
  }
  if (score >= 60) {
    return "warning" as const;
  }
  return "danger" as const;
}

function tokenizeText(value: string) {
  return value.match(/[\u4e00-\u9fff]+|[A-Za-z0-9_+-]+|\s+|[^\sA-Za-z0-9\u4e00-\u9fff]/g) ?? [];
}

function buildHighlightedSegments(source: string, revised: string): DiffSegment[] {
  if (!revised.trim()) {
    return [];
  }

  const sourceTokens = tokenizeText(source);
  const revisedTokens = tokenizeText(revised);

  if (sourceTokens.length === 0) {
    return [{ text: revised, changed: true }];
  }

  const rows = sourceTokens.length;
  const cols = revisedTokens.length;
  const dp = Array.from({ length: rows + 1 }, () => Array<number>(cols + 1).fill(0));

  for (let i = rows - 1; i >= 0; i -= 1) {
    for (let j = cols - 1; j >= 0; j -= 1) {
      dp[i][j] =
        sourceTokens[i] === revisedTokens[j]
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const changedFlags = Array<boolean>(cols).fill(true);
  let i = 0;
  let j = 0;

  while (i < rows && j < cols) {
    if (sourceTokens[i] === revisedTokens[j]) {
      changedFlags[j] = false;
      i += 1;
      j += 1;
      continue;
    }

    if (dp[i + 1][j] >= dp[i][j + 1]) {
      i += 1;
    } else {
      j += 1;
    }
  }

  const segments: DiffSegment[] = [];
  revisedTokens.forEach((token, index) => {
    const previous = segments[segments.length - 1];
    if (previous && previous.changed === changedFlags[index]) {
      previous.text += token;
      return;
    }
    segments.push({ text: token, changed: changedFlags[index] });
  });

  return segments;
}

export function ResumeRevisionPanel({
  job,
  revising,
  streamingContent,
  result,
  onRevise,
}: ResumeRevisionPanelProps) {
  const [resumeText, setResumeText] = useState("");
  const [uploadFeedback, setUploadFeedback] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const parseDocumentMutation = useParseResumeDocument();

  useEffect(() => {
    if (!job) {
      setResumeText("");
      setUploadFeedback(null);
    }
  }, [job]);

  const highlightedSegments = useMemo(
    () => buildHighlightedSegments(resumeText, result?.revised_resume ?? ""),
    [resumeText, result?.revised_resume],
  );

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      const response = await parseDocumentMutation.mutateAsync(file);
      setResumeText(response.extracted_text);
      setUploadFeedback(`已从《${response.filename}》提取文本并填充到输入框。`);
    } catch (error) {
      setUploadFeedback(getErrorMessage(error));
    } finally {
      event.target.value = "";
    }
  }

  return (
    <Card title="简历修订" subtitle="先修订简历，再基于当前简历内容给出岗位匹配度评分。">
      {!job ? (
        <EmptyState title="等待岗位" description="先创建或选择一条岗位，再输入或上传简历进行修订。" />
      ) : (
        <div className="stack">
          <div className="section-actions">
            <div className="panel-actions panel-actions-tight">
              <Button
                type="button"
                variant="secondary"
                className="btn-pill"
                onClick={() => fileInputRef.current?.click()}
                disabled={parseDocumentMutation.isPending || revising}
              >
                {parseDocumentMutation.isPending ? "解析中..." : "上传图片 / PDF"}
              </Button>
              <Button
                variant="ghost"
                className="btn-pill"
                onClick={() => result?.revised_resume && copyText(result.revised_resume)}
                disabled={!result?.revised_resume || revising}
              >
                复制修订结果
              </Button>
              <Button className="btn-hero" onClick={() => onRevise(resumeText)} disabled={revising}>
                {revising ? "修订中..." : "修订简历并评分"}
              </Button>
            </div>
          </div>

          <Field label="原始简历" hint="支持手动粘贴，或上传 PDF / 图片自动提取文本">
            <textarea
              className="text-area text-area-tall"
              value={resumeText}
              onChange={(event) => setResumeText(event.target.value)}
            />
          </Field>

          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            className="file-input-hidden"
            onChange={(event) => void handleFileChange(event)}
          />

          <div className="upload-hint upload-hint-bar">仅支持 PDF / 图片文件，单文件大小不超过 10MB。</div>

          {uploadFeedback && (
            <div className={parseDocumentMutation.isError ? "error-banner" : "success-banner"}>{uploadFeedback}</div>
          )}

          {revising ? (
            <div className="content-box">
              <div className="detail-label">流式输出中</div>
              <div>{streamingContent || "模型正在生成修订结果..."}</div>
            </div>
          ) : result ? (
            <div className="stack">
              <div className="analysis-score-card">
                <div className="detail-label">修订后匹配度评分</div>
                <div className="analysis-score-value">
                  {result.match_score ?? "--"}
                  <span>/ 100</span>
                </div>
                <StatusPill tone={getScoreTone(result.match_score)}>
                  {result.match_score === null ? "待生成" : "基于当前简历与岗位的匹配度"}
                </StatusPill>
              </div>

              {result.match_explanation && (
                <div className="content-box">
                  <div className="detail-label">评分说明</div>
                  <div>{result.match_explanation}</div>
                </div>
              )}

              <div className="revision-diff-note">
                <div className="detail-label">高亮说明</div>
                <div className="revision-diff-legend">
                  <span className="revision-diff-badge">高亮部分</span>
                  <span>表示 AI 相比原简历新增或改写的表述。</span>
                </div>
                <div className="revision-diff-legend">
                  <span className="revision-diff-badge revision-diff-badge-muted">未高亮部分</span>
                  <span>表示与原简历基本一致或仅有轻微格式调整。</span>
                </div>
              </div>

              <div className="content-box">
                <div className="detail-label">修订结果</div>
                <div className="revision-diff-text">
                  {highlightedSegments.map((segment, index) => (
                    <Fragment key={`${index}-${segment.changed ? "changed" : "same"}`}>
                      {segment.changed ? (
                        <mark className="revision-diff-mark">{segment.text}</mark>
                      ) : (
                        <span>{segment.text}</span>
                      )}
                    </Fragment>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <EmptyState title="尚未生成修订结果" description="上传或输入简历后，点击“修订简历并评分”查看输出。" />
          )}
        </div>
      )}
    </Card>
  );
}
