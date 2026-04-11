export type JobCreateInput = {
  title: string;
  company: string;
  source?: string;
  jd_text: string;
};

export type JobUpdateInput = JobCreateInput;

export type JobResponse = {
  id: number;
  title: string;
  company: string;
  source: string | null;
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
