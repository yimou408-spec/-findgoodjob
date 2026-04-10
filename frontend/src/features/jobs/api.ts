import { apiRequest } from "../../shared/api/client";
import type {
  AnalyzeJobResponse,
  JobCreateInput,
  JobResponse,
  ResumeRevisionInput,
  ResumeRevisionResponse,
} from "./types";

export function getJobs() {
  return apiRequest<JobResponse[]>("/jobs");
}

export function createJob(input: JobCreateInput) {
  return apiRequest<JobResponse>("/jobs", {
    method: "POST",
    // 这里传原始对象即可，请求层会统一完成 JSON 序列化。
    body: input,
  });
}

export function getJob(jobId: number) {
  return apiRequest<JobResponse>(`/jobs/${jobId}`);
}

export function analyzeJob(jobId: number) {
  return apiRequest<AnalyzeJobResponse>(`/jobs/${jobId}/analyze`, {
    method: "POST",
  });
}

export function reviseResume(jobId: number, input: ResumeRevisionInput) {
  return apiRequest<ResumeRevisionResponse>(`/jobs/${jobId}/revise-resume`, {
    method: "POST",
    body: input,
  });
}

export function getHealth() {
  return apiRequest<{ status: string }>("/health");
}
