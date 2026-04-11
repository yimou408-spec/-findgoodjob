import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { StatusPill } from "../../../shared/ui/StatusPill";
import type { JobResponse } from "../types";

type JobDetailPanelProps = {
  job: JobResponse | null;
  loading: boolean;
};

export function JobDetailPanel({ job, loading }: JobDetailPanelProps) {
  return (
    <Card title="岗位工作区" subtitle="查看岗位详情、JD 原文以及当前分析状态。">
      {loading ? (
        <div className="content-box">岗位详情加载中...</div>
      ) : !job ? (
        <EmptyState title="未选中岗位" description="先从左侧选择一条岗位，或创建新的岗位 JD。" />
      ) : (
        <div className="stack">
          <div className="inline-actions">
            <StatusPill tone="neutral">{job.company}</StatusPill>
            <StatusPill tone={job.analysis_result ? "success" : "warning"}>
              {job.analysis_result ? "分析完成" : "等待分析"}
            </StatusPill>
          </div>

          <div className="detail-block">
            <span className="detail-label">岗位名称</span>
            <strong>{job.title}</strong>
          </div>

          <div className="detail-block">
            <span className="detail-label">岗位 JD</span>
            <div className="content-box">{job.jd_text}</div>
          </div>
        </div>
      )}
    </Card>
  );
}
