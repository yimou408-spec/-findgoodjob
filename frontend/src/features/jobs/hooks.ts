import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { analyzeJob, createJob, deleteJob, getHealth, getJob, getJobs, parseResumeDocument, reviseResume, updateJob } from "./api";
import type { JobCreateInput, JobUpdateInput, ResumeRevisionInput } from "./types";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10000,
  });
}

export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: getJobs,
  });
}

export function useJob(jobId: number | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as number),
    enabled: jobId !== null,
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: JobCreateInput) => createJob(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useUpdateJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ jobId, input }: { jobId: number; input: JobUpdateInput }) => updateJob(jobId, input),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job", job.id] });
    },
  });
}

export function useDeleteJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: number) => deleteJob(jobId),
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.removeQueries({ queryKey: ["job", jobId] });
    },
  });
}

export function useAnalyzeJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: number) => analyzeJob(jobId),
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useReviseResume() {
  return useMutation({
    mutationFn: ({ jobId, input }: { jobId: number; input: ResumeRevisionInput }) =>
      reviseResume(jobId, input),
  });
}

export function useParseResumeDocument() {
  return useMutation({
    mutationFn: (file: File) => parseResumeDocument(file),
  });
}
