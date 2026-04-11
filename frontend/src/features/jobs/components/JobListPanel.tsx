import type { ReactNode } from "react";

import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { StatusPill } from "../../../shared/ui/StatusPill";
import type { JobResponse } from "../types";

type JobListPanelProps = {
  jobs: JobResponse[];
  selectedJobId: number | null;
  editingJobId?: number | null;
  deletingJobId?: number | null;
  onSelect: (jobId: number) => void;
  onEdit: (job: JobResponse) => void;
  onDelete: (job: JobResponse) => void;
  actions?: ReactNode;
};

function getStatusTone(job: JobResponse) {
  return job.analysis_result ? ("success" as const) : ("neutral" as const);
}

export function JobListPanel({
  jobs,
  selectedJobId,
  editingJobId,
  deletingJobId,
  onSelect,
  onEdit,
  onDelete,
  actions,
}: JobListPanelProps) {
  return (
    <Card title="岗位列表" subtitle="这里展示数据库中的真实岗位记录。" actions={actions}>
      {jobs.length === 0 ? (
        <EmptyState title="还没有岗位" description="先创建一条岗位 JD，再进入岗位分析和简历修订。" />
      ) : (
        <div className="job-list">
          {jobs.map((job) => (
            <button
              key={job.id}
              className={`job-list-item ${selectedJobId === job.id ? "job-list-item-active" : ""}`}
              onClick={() => onSelect(job.id)}
              type="button"
            >
              <div className="job-list-header">
                <div className="job-list-heading">
                  <h3>{job.title}</h3>
                  <div className="job-list-meta">{job.company}</div>
                </div>
                <div className="job-list-actions">
                  <Button
                    type="button"
                    variant="ghost"
                    className="btn-chip"
                    disabled={editingJobId === job.id}
                    onClick={(event) => {
                      event.stopPropagation();
                      onEdit(job);
                    }}
                  >
                    {editingJobId === job.id ? "编辑中..." : "编辑"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="btn-chip btn-danger-ghost"
                    disabled={deletingJobId === job.id}
                    onClick={(event) => {
                      event.stopPropagation();
                      onDelete(job);
                    }}
                  >
                    {deletingJobId === job.id ? "处理中..." : "删除"}
                  </Button>
                </div>
              </div>
              <div className="job-list-footer">
                <StatusPill tone={getStatusTone(job)}>{job.analysis_result ? "已分析" : "待分析"}</StatusPill>
                <span className="job-list-meta">ID {job.id}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}
