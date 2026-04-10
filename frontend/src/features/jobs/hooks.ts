import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { analyzeJob, createJob, getHealth, getJob, getJobs, reviseResume } from "./api";
import type { JobCreateInput, ResumeRevisionInput } from "./types";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10000,
  });
}

// React Query 统一管理服务端状态，避免页面自己维护列表缓存和刷新时机。
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
