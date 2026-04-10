export type JobCreateInput = {
  title: string;
  company: string;
  source?: string;
  jd_text: string;
};

export type JobResponse = {
  id: number;
  title: string;
  company: string;
  source: string | null;
  jd_text: string;
  analysis_result: string | null;
};

export type AnalyzeJobResponse = {
  job_id: number;
  analysis_result: string;
};

export type ResumeRevisionInput = {
  resume_text: string;
};

export type ResumeRevisionResponse = {
  job_id: number;
  revised_resume: string;
};
