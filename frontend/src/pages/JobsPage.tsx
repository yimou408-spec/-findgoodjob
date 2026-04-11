import { useEffect, useMemo, useState } from "react";

import { HealthBadge } from "../features/jobs/components/HealthBadge";
import { JobAnalysisPanel } from "../features/jobs/components/JobAnalysisPanel";
import { JobCreateModal } from "../features/jobs/components/JobCreateModal";
import { JobDeleteDialog } from "../features/jobs/components/JobDeleteDialog";
import { JobDetailPanel } from "../features/jobs/components/JobDetailPanel";
import { JobListPanel } from "../features/jobs/components/JobListPanel";
import { ResumeRevisionPanel } from "../features/jobs/components/ResumeRevisionPanel";
import {
  useAnalyzeJob,
  useCreateJob,
  useDeleteJob,
  useJob,
  useJobs,
  useReviseResume,
  useUpdateJob,
} from "../features/jobs/hooks";
import type { JobCreateInput, JobResponse, ResumeRevisionResponse } from "../features/jobs/types";
import { ApiError } from "../shared/api/client";
import { Button } from "../shared/ui/Button";
import { EmptyState } from "../shared/ui/EmptyState";
import { StatusPill } from "../shared/ui/StatusPill";

const STORAGE_KEY = "findgoodjob.selected.job.id";

function loadSelectedJobId() {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw ? Number(raw) : null;
}

function saveSelectedJobId(jobId: number | null) {
  if (jobId === null) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, String(jobId));
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "发生未知错误，请稍后重试。";
}

function toJobForm(job: JobResponse): JobCreateInput {
  return {
    title: job.title,
    company: job.company,
    source: job.source ?? undefined,
    jd_text: job.jd_text,
  };
}

export function JobsPage() {
  const [selectedJobId, setSelectedJobId] = useState<number | null>(() => loadSelectedJobId());
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editingJob, setEditingJob] = useState<JobResponse | null>(null);
  const [deletingJob, setDeletingJob] = useState<JobResponse | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [resumeResult, setResumeResult] = useState<ResumeRevisionResponse | null>(null);

  const jobsQuery = useJobs();
  const createJobMutation = useCreateJob();
  const updateJobMutation = useUpdateJob();
  const deleteJobMutation = useDeleteJob();
  const analyzeJobMutation = useAnalyzeJob();
  const reviseResumeMutation = useReviseResume();
  const selectedJobQuery = useJob(selectedJobId);

  useEffect(() => {
    const jobs = jobsQuery.data ?? [];
    if (jobs.length === 0) {
      setSelectedJobId(null);
      saveSelectedJobId(null);
      return;
    }

    const stillExists = selectedJobId !== null && jobs.some((job) => job.id === selectedJobId);
    if (!stillExists) {
      const nextSelectedJobId = jobs[0].id;
      setSelectedJobId(nextSelectedJobId);
      saveSelectedJobId(nextSelectedJobId);
    }
  }, [jobsQuery.data, selectedJobId]);

  useEffect(() => {
    saveSelectedJobId(selectedJobId);
  }, [selectedJobId]);

  const jobs = jobsQuery.data ?? [];
  const selectedJob = selectedJobQuery.data ?? null;

  const sessionStats = useMemo(
    () => ({
      total: jobs.length,
      analyzed: jobs.filter((job) => job.analysis_result).length,
    }),
    [jobs],
  );

  async function handleCreateJob(input: JobCreateInput) {
    try {
      const created = await createJobMutation.mutateAsync(input);
      setSelectedJobId(created.id);
      setCreateModalOpen(false);
      setResumeResult(null);
      setFeedback({ type: "success", message: `岗位《${created.title}》已创建，可继续分析和修订简历。` });
    } catch (error) {
      setFeedback({ type: "error", message: getErrorMessage(error) });
    }
  }

  async function handleUpdateJob(input: JobCreateInput) {
    if (!editingJob) {
      return;
    }

    try {
      const updated = await updateJobMutation.mutateAsync({ jobId: editingJob.id, input });
      setEditingJob(null);
      setSelectedJobId(updated.id);
      setResumeResult(null);
      setFeedback({ type: "success", message: `岗位《${updated.title}》已更新，列表与详情已同步刷新。` });
    } catch (error) {
      setFeedback({ type: "error", message: getErrorMessage(error) });
    }
  }

  async function handleDeleteJob() {
    if (!deletingJob) {
      return;
    }

    const target = deletingJob;

    try {
      await deleteJobMutation.mutateAsync(target.id);
      if (selectedJobId === target.id) {
        setSelectedJobId(null);
        setResumeResult(null);
      }
      setDeletingJob(null);
      setFeedback({ type: "success", message: `岗位《${target.title}》已删除。` });
    } catch (error) {
      setFeedback({ type: "error", message: getErrorMessage(error) });
    }
  }

  async function handleAnalyzeJob() {
    if (!selectedJobId) {
      return;
    }

    try {
      await analyzeJobMutation.mutateAsync(selectedJobId);
      setFeedback({ type: "success", message: "岗位分析已完成，结果已更新到中间工作区。" });
    } catch (error) {
      setFeedback({ type: "error", message: getErrorMessage(error) });
    }
  }

  async function handleReviseResume(resumeText: string) {
    if (!selectedJobId) {
      return;
    }

    try {
      const response = await reviseResumeMutation.mutateAsync({
        jobId: selectedJobId,
        input: { resume_text: resumeText },
      });
      setResumeResult(response);
      setFeedback({ type: "success", message: "简历修订已完成，右侧已同步展示匹配度评分与修订结果。" });
    } catch (error) {
      setFeedback({ type: "error", message: getErrorMessage(error) });
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1 className="app-title">FindGoodJob Console</h1>
          <p className="app-subtitle">
            为当前 FastAPI 后端设计的一体化求职 Agent 工作台。左侧维护岗位流转，中间做岗位分析，右侧直接完成简历修订。
          </p>
        </div>
        <div className="header-meta">
          <HealthBadge />
          <StatusPill tone="neutral">开发环境</StatusPill>
          <StatusPill tone={sessionStats.analyzed > 0 ? "success" : "warning"}>
            已分析 {sessionStats.analyzed} / {sessionStats.total}
          </StatusPill>
        </div>
      </header>

      {feedback && (
        <div className={feedback.type === "success" ? "success-banner" : "error-banner"}>{feedback.message}</div>
      )}

      <div className="workspace-grid">
        <JobListPanel
          jobs={jobs}
          selectedJobId={selectedJobId}
          editingJobId={updateJobMutation.isPending ? editingJob?.id ?? null : null}
          deletingJobId={deleteJobMutation.isPending ? deletingJob?.id ?? null : null}
          onSelect={(jobId) => {
            setSelectedJobId(jobId);
            setResumeResult(null);
          }}
          onEdit={(job) => setEditingJob(job)}
          onDelete={(job) => setDeletingJob(job)}
          actions={<Button onClick={() => setCreateModalOpen(true)}>新增岗位</Button>}
        />

        <div className="stack">
          <JobDetailPanel job={selectedJob} loading={selectedJobQuery.isLoading} />
          <JobAnalysisPanel
            job={selectedJob}
            loading={selectedJobQuery.isLoading}
            analyzing={analyzeJobMutation.isPending}
            onAnalyze={handleAnalyzeJob}
          />
        </div>

        <ResumeRevisionPanel
          job={selectedJob}
          revising={reviseResumeMutation.isPending}
          result={resumeResult}
          onRevise={handleReviseResume}
        />
      </div>

      {!jobsQuery.isLoading && jobs.length === 0 && (
        <div style={{ marginTop: 18 }}>
          <EmptyState
            title="推荐先创建一条 AI 产品岗位"
            description="这个工作台已经连接数据库岗位列表。你可以先创建一条岗位，再立刻分析和修订简历。"
            action={<Button onClick={() => setCreateModalOpen(true)}>立即创建岗位</Button>}
          />
        </div>
      )}

      <JobCreateModal
        open={createModalOpen}
        submitting={createJobMutation.isPending}
        onClose={() => setCreateModalOpen(false)}
        onSubmit={handleCreateJob}
      />

      <JobCreateModal
        open={editingJob !== null}
        mode="edit"
        initialValues={editingJob ? toJobForm(editingJob) : undefined}
        submitting={updateJobMutation.isPending}
        onClose={() => setEditingJob(null)}
        onSubmit={handleUpdateJob}
      />

      <JobDeleteDialog
        open={deletingJob !== null}
        job={deletingJob}
        deleting={deleteJobMutation.isPending}
        onClose={() => setDeletingJob(null)}
        onConfirm={handleDeleteJob}
      />
    </div>
  );
}
