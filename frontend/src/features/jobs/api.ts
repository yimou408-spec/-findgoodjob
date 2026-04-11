import { API_BASE_URL, ApiError, apiRequest, parseApiError } from "../../shared/api/client";
import type {
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantThreadResponse,
  AnalyzeJobResponse,
  JobCreateInput,
  JobResponse,
  JobUpdateInput,
  ResumeDocumentParseResponse,
  ResumeRevisionInput,
  ResumeRevisionResponse,
} from "./types";

type StreamEvent<T> =
  | { type: "start" }
  | { type: "chunk"; delta: string; content: string }
  | { type: "complete"; content: string; data: T }
  | { type: "error"; detail: string; error_code?: string };

type StreamRequestOptions<TInput, TOutput> = {
  path: string;
  body?: TInput;
  onChunk?: (content: string, delta: string) => void;
};

async function streamApiRequest<TInput, TOutput>({
  path,
  body,
  onChunk,
}: StreamRequestOptions<TInput, TOutput>): Promise<TOutput> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  if (!response.body) {
    throw new ApiError("流式响应不可用，请稍后重试", 500, "stream_unavailable");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalData: TOutput | null = null;

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    let boundaryIndex = buffer.indexOf("\n\n");
    while (boundaryIndex !== -1) {
      const rawEvent = buffer.slice(0, boundaryIndex);
      buffer = buffer.slice(boundaryIndex + 2);

      const dataLine = rawEvent
        .split("\n")
        .find((line) => line.startsWith("data:"));

      if (dataLine) {
        const parsed = JSON.parse(dataLine.slice(5).trim()) as StreamEvent<TOutput>;
        if (parsed.type === "chunk") {
          onChunk?.(parsed.content, parsed.delta);
        } else if (parsed.type === "complete") {
          finalData = parsed.data;
          onChunk?.(parsed.content, "");
        } else if (parsed.type === "error") {
          throw new ApiError(parsed.detail, 502, parsed.error_code);
        }
      }

      boundaryIndex = buffer.indexOf("\n\n");
    }

    if (done) {
      break;
    }
  }

  if (finalData === null) {
    throw new ApiError("流式响应未返回最终结果", 500, "stream_incomplete");
  }

  return finalData;
}

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

export function streamAnalyzeJob(jobId: number, onChunk?: (content: string, delta: string) => void) {
  return streamApiRequest<undefined, AnalyzeJobResponse>({
    path: `/jobs/${jobId}/analyze/stream`,
    onChunk,
  });
}

export function reviseResume(jobId: number, input: ResumeRevisionInput) {
  return apiRequest<ResumeRevisionResponse>(`/jobs/${jobId}/revise-resume`, {
    method: "POST",
    body: input,
  });
}

export function streamReviseResume(
  jobId: number,
  input: ResumeRevisionInput,
  onChunk?: (content: string, delta: string) => void,
) {
  return streamApiRequest<ResumeRevisionInput, ResumeRevisionResponse>({
    path: `/jobs/${jobId}/revise-resume/stream`,
    body: input,
    onChunk,
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

export function getAssistantThread(jobId: number) {
  return apiRequest<AssistantThreadResponse>(`/jobs/${jobId}/assistant/thread`);
}

export function streamAssistantChat(
  jobId: number,
  input: AssistantChatRequest,
  onChunk?: (content: string, delta: string) => void,
) {
  return streamApiRequest<AssistantChatRequest, AssistantChatResponse>({
    path: `/jobs/${jobId}/assistant/chat/stream`,
    body: input,
    onChunk,
  });
}
