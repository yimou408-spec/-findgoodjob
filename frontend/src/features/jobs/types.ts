export type JobCreateInput = {
  title: string;
  company: string;
  jd_text: string;
};

export type JobUpdateInput = JobCreateInput;

export type JobResponse = {
  id: number;
  title: string;
  company: string;
  jd_text: string;
  analysis_result: string | null;
  analysis_improvement_advice: string | null;
};

export type AnalyzeJobResponse = {
  job_id: number;
  analysis_result: string;
  analysis_improvement_advice: string | null;
};

export type ResumeRevisionInput = {
  resume_text: string;
};

export type ResumeRevisionResponse = {
  job_id: number;
  revised_resume: string;
  match_score: number | null;
  match_explanation: string | null;
};

export type ResumeDocumentParseResponse = {
  filename: string;
  content_type: string;
  extracted_text: string;
};

export type ResumeRevisionRecord = {
  id: number;
  job_id: number;
  source_resume_text: string;
  revised_resume: string;
  match_score: number | null;
  match_explanation: string | null;
  created_at: string | null;
};

export type AssistantMessage = {
  id: number;
  role: "assistant" | "user";
  content: string;
  sequence: number;
  created_at: string | null;
};

export type AssistantThreadResponse = {
  thread_id: number;
  job_id: number;
  can_chat: boolean;
  summary_text: string | null;
  workspace_summary: string;
  messages: AssistantMessage[];
  latest_resume_revision: ResumeRevisionRecord | null;
};

export type AssistantChatRequest = {
  message: string;
};

export type AssistantChatResponse = {
  thread_id: number;
  job_id: number;
  message: AssistantMessage;
  summary_text: string | null;
  workspace_summary: string;
};
