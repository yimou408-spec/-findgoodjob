import type { ReactNode } from "react";

import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { StatusPill } from "../../../shared/ui/StatusPill";
import type { JobResponse } from "../types";

type JobListPanelProps = {
  jobs: JobResponse[];
  selectedJobId: number | null;
  onSelect: (jobId: number) => void;
  actions?: ReactNode;
};

function getStatusTone(job: JobResponse) {
  return job.analysis_result ? ("success" as const) : ("neutral" as const);
}

export function JobListPanel({ jobs, selectedJobId, onSelect, actions }: JobListPanelProps) {
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
              <h3>{job.title}</h3>
              <div className="job-list-meta">{job.company}</div>
              <div className="job-list-footer">
                <StatusPill tone={getStatusTone(job)}>
                  {job.analysis_result ? "已分析" : "待分析"}
                </StatusPill>
                <span className="job-list-meta">ID {job.id}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}
