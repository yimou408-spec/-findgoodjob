import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { copyText } from "../../../shared/utils/clipboard";
import type { JobResponse } from "../types";

type JobAnalysisPanelProps = {
  job: JobResponse | null;
  loading: boolean;
  analyzing: boolean;
  onAnalyze: () => Promise<void>;
};

export function JobAnalysisPanel({ job, loading, analyzing, onAnalyze }: JobAnalysisPanelProps) {
  return (
    <Card
      title="岗位分析"
      subtitle="调用 DeepSeek 对当前岗位 JD 做结构化分析。"
      actions={
        <div className="inline-actions">
          <Button
            variant="secondary"
            onClick={() => job?.analysis_result && copyText(job.analysis_result)}
            disabled={!job?.analysis_result}
          >
            复制分析结果
          </Button>
          <Button onClick={onAnalyze} disabled={!job || analyzing}>
            {analyzing ? "分析中..." : "分析岗位"}
          </Button>
        </div>
      }
    >
      {loading ? (
        <div className="content-box">岗位分析加载中...</div>
      ) : !job ? (
        <EmptyState title="暂无岗位分析" description="选择岗位后点击“分析岗位”，这里会展示结构化结果。" />
      ) : job.analysis_result ? (
        <div className="content-box">{job.analysis_result}</div>
      ) : (
        <EmptyState title="还未分析" description="当前岗位已经准备就绪，点击上方按钮即可触发分析。" />
      )}
    </Card>
  );
}
