import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { copyText } from "../../../shared/utils/clipboard";
import type { JobResponse } from "../types";

type JobAnalysisPanelProps = {
  job: JobResponse | null;
  loading: boolean;
  analyzing: boolean;
  streamingContent: string;
  onAnalyze: () => Promise<void>;
};

function adviceToList(advice: string | null) {
  if (!advice) {
    return [];
  }

  return advice
    .split("\n")
    .map((item) => item.replace(/^-+\s*/, "").trim())
    .filter(Boolean);
}

export function JobAnalysisPanel({ job, loading, analyzing, streamingContent, onAnalyze }: JobAnalysisPanelProps) {
  const adviceItems = adviceToList(job?.analysis_improvement_advice ?? null);

  return (
    <Card
      title="岗位分析"
      subtitle="基于当前岗位 JD 生成分析摘要和简历优化建议。匹配度评分会在简历修订后展示。"
      actions={
        <div className="panel-actions">
          <Button
            variant="secondary"
            className="btn-pill"
            onClick={() => job?.analysis_improvement_advice && copyText(job.analysis_improvement_advice)}
            disabled={!job?.analysis_improvement_advice || analyzing}
          >
            复制改进建议
          </Button>
          <Button
            variant="secondary"
            className="btn-pill"
            onClick={() => job?.analysis_result && copyText(job.analysis_result)}
            disabled={!job?.analysis_result || analyzing}
          >
            复制分析摘要
          </Button>
          <Button className="btn-hero" onClick={onAnalyze} disabled={!job || analyzing}>
            {analyzing ? "分析中..." : "分析岗位"}
          </Button>
        </div>
      }
    >
      {loading ? (
        <div className="content-box">岗位分析加载中...</div>
      ) : !job ? (
        <EmptyState title="暂无岗位分析" description="选择岗位后点击“分析岗位”，这里会展示结构化结果。" />
      ) : analyzing ? (
        <div className="analysis-grid">
          <div className="content-box">
            <div className="detail-label">流式输出中</div>
            <div>{streamingContent || "模型正在组织分析内容..."}</div>
          </div>
        </div>
      ) : job.analysis_result ? (
        <div className="analysis-grid">
          <div className="content-box">
            <div className="detail-label">改进建议</div>
            {adviceItems.length > 0 ? (
              <ul className="analysis-list">
                {adviceItems.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <div className="analysis-note">暂无改进建议</div>
            )}
          </div>

          <div className="content-box">
            <div className="detail-label">分析摘要</div>
            <div>{job.analysis_result}</div>
          </div>
        </div>
      ) : (
        <EmptyState title="还未分析" description="当前岗位已经准备就绪，点击上方按钮即可触发分析。" />
      )}
    </Card>
  );
}
