import { type ChangeEvent, useEffect, useRef, useState } from "react";

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
  result: ResumeRevisionResponse | null;
  onRevise: (resumeText: string) => Promise<void>;
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

export function ResumeRevisionPanel({ job, revising, result, onRevise }: ResumeRevisionPanelProps) {
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
          <Field label="原始简历" hint="支持手动粘贴，或上传 PDF / 图片自动提取文本">
            <textarea className="text-area" value={resumeText} onChange={(event) => setResumeText(event.target.value)} />
          </Field>

          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            className="file-input-hidden"
            onChange={(event) => void handleFileChange(event)}
          />

          <div className="inline-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={parseDocumentMutation.isPending}
            >
              {parseDocumentMutation.isPending ? "解析中..." : "上传图片 / PDF"}
            </Button>
            <Button onClick={() => onRevise(resumeText)} disabled={revising}>
              {revising ? "修订中..." : "修订简历并评分"}
            </Button>
            <Button variant="ghost" onClick={() => result?.revised_resume && copyText(result.revised_resume)} disabled={!result?.revised_resume}>
              复制修订结果
            </Button>
          </div>

          <div className="upload-hint">仅支持 PDF / 图片文件，单文件大小不超过 10MB。</div>

          {uploadFeedback && (
            <div className={parseDocumentMutation.isError ? "error-banner" : "success-banner"}>{uploadFeedback}</div>
          )}

          {result ? (
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

              <div className="content-box">
                <div className="detail-label">修订结果</div>
                <div>{result.revised_resume}</div>
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
