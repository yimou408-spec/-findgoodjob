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
  retrieval_note?: string | null;
  source_links?: string[];
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

export type InterviewKnowledgeImportItem = {
  source_id?: string | null;
  url?: string | null;
  title?: string | null;
  author_name?: string | null;
  published_at?: string | null;
  crawl_at?: string | null;
  company?: string | null;
  role?: string | null;
  interview_stage?: string | null;
  city?: string | null;
  tags?: string[];
  quality_score?: number | null;
  content_raw: string;
  content_summary?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type InterviewKnowledgeImportRequest = {
  items: InterviewKnowledgeImportItem[];
};

export type InterviewKnowledgeSourceResponse = {
  id: number;
  source_platform: string;
  source_type: string;
  source_id: string | null;
  url: string | null;
  title: string | null;
  author_name: string | null;
  published_at: string | null;
  crawl_at: string | null;
  ingest_at: string | null;
  company: string | null;
  role: string | null;
  interview_stage: string | null;
  city: string | null;
  tags: string[];
  quality_score: number | null;
  compliance_status: string;
  content_clean: string;
  content_summary: string;
  updated_at: string | null;
  chunk_count: number;
  embedding_ready: boolean;
};

export type InterviewKnowledgeImportResponse = {
  imported_count: number;
  source_platform: string;
  compliance_status: string;
  sources: InterviewKnowledgeSourceResponse[];
};

export type InterviewKnowledgeSourceListResponse = {
  total_count: number;
  sources: InterviewKnowledgeSourceResponse[];
};

export type InterviewKnowledgeCompileLinksRequest = {
  links: string[];
  default_company?: string | null;
  default_role?: string | null;
  default_city?: string | null;
  compliance_status?: string | null;
};

export type InterviewKnowledgeCompileResult = {
  url: string;
  status: string;
  error: string | null;
  source_id: string | null;
  title: string | null;
  company: string | null;
  role: string | null;
  interview_stage: string | null;
  city: string | null;
  content_summary: string | null;
};

export type InterviewKnowledgeCompileLinksResponse = {
  requested_count: number;
  compiled_count: number;
  imported_count: number;
  failed_count: number;
  results: InterviewKnowledgeCompileResult[];
};

export type InterviewKnowledgeSearchResult = {
  source_record_id: number;
  source_platform: string;
  source_type: string;
  source_id: string | null;
  url: string | null;
  title: string | null;
  company: string | null;
  role: string | null;
  interview_stage: string | null;
  city: string | null;
  content_summary: string;
  chunk_text: string;
  score: number;
  compliance_status: string;
};

export type InterviewKnowledgeSearchResponse = {
  query: string;
  result_count: number;
  results: InterviewKnowledgeSearchResult[];
};

export type InterviewKnowledgeReindexResponse = {
  knowledge_base_job_id: number;
  source_count: number;
  document_count: number;
  chunk_count: number;
};
