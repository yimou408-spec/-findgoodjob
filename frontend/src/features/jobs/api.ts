import { apiRequest } from "../../shared/api/client";
import type {
  AnalyzeJobResponse,
  JobCreateInput,
  JobResponse,
  ResumeDocumentParseResponse,
  JobUpdateInput,
  ResumeRevisionInput,
  ResumeRevisionResponse,
} from "./types";

export function getJobs() {
  return apiRequest<JobResponse[]>("/jobs");
}

export function createJob(input: JobCreateInput) {
  return apiRequest<JobResponse>("/jobs", {
    method: "POST",
    body: input,
  });
}

export function updateJob(jobId: number, input: JobUpdateInput) {
  return apiRequest<JobResponse>(`/jobs/${jobId}`, {
    method: "PUT",
    body: input,
  });
}

export function deleteJob(jobId: number) {
  return apiRequest<null>(`/jobs/${jobId}`, {
    method: "DELETE",
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

export function parseResumeDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  return apiRequest<ResumeDocumentParseResponse>("/resume/parse-document", {
    method: "POST",
    body: formData,
  });
}

export function getHealth() {
  return apiRequest<{ status: string }>("/health");
}
