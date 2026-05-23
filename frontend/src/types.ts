// ════════════════════════════════════════════
// RecruitAgent 共享类型定义
// ════════════════════════════════════════════

// ─── 岗位需求 (JD) ───

export interface JobDescription {
  id: number;
  title: string;
  department?: string;
  content: string;
  original_content?: string;
  status: 'pending' | 'approved' | 'rejected' | 'draft';
  created_at: string;
  updated_at?: string;
  label: string; // "前端开发（技术部）"
}

// ─── 简历 ───

export type ResumeStatus = 'pending' | 'ai_pass' | 'ai_reject' | 'manual_pass' | 'manual_reject';

export interface ResumeAnalysis {
  project_authenticity?: {
    score: number;
    details?: string;
    flags?: string[];
  };
  risk_warnings?: Array<{
    severity: 'low' | 'medium' | 'high';
    type: string;
    detail: string;
  }>;
  frequent_job_change?: boolean;
  career_trajectory?: {
    score: number;
    details?: string;
  };
  [key: string]: unknown;
}

export interface Resume {
  id: number;
  name?: string;
  file_name: string;
  raw_text?: string;
  skills?: string;
  experience_years?: number;
  education?: string;
  ai_score?: number;
  ai_recommended?: boolean;
  ai_reason?: string;
  status: ResumeStatus;
  deep_analysis?: ResumeAnalysis;
  notes?: string;
  jd_id?: number;
  jd_title?: string;
  created_at: string;
  updated_at?: string;
}

export interface ResumeListResponse {
  items: Resume[];
  total: number;
  page: number;
  page_size: number;
}

// ─── 面试 ───

export type InterviewRound = 'first' | 'second' | 'third' | 'hr';
export type InterviewStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled';

export interface Interview {
  id: number;
  resume_id: number;
  jd_id?: number;
  round: InterviewRound;
  interviewer_name?: string;
  interviewer_email?: string;
  candidate_name: string;
  candidate_email?: string;
  scheduled_at?: string;
  duration_minutes?: number;
  meeting_link?: string;
  status: InterviewStatus;
  notes?: string;
  created_at: string;
  prev_evaluations?: InterviewEvaluation[];
}

export interface InterviewCreatePayload {
  resume_id: number;
  round: string;
  interviewer_name: string;
  interviewer_email?: string;
  candidate_name?: string;
  candidate_email?: string;
  meeting_link?: string;
  scheduled_at?: string;
  duration_minutes?: number;
}

export interface InterviewEvaluation {
  id?: number;
  interview_id?: number;
  evaluator?: string;
  tech_score?: number;
  experience_score?: number;
  communication_score?: number;
  collaboration_score?: number;
  overall_score?: number;
  strengths?: string;
  weaknesses?: string;
  conclusion?: string;
  recommendation?: 'pass' | 'hold' | 'reject';
  rating_level?: 'excellent' | 'good' | 'average';
  notes?: string;
  created_at?: string;
  round?: string;
  round_label?: string;
}

export interface PipelineRound {
  round: string;
  label: string;
  count: number;
  interviews: Interview[];
}

export interface PipelineResponse {
  pipeline: PipelineRound[];
  total: number;
}

// ─── 面试官 ───

export interface Interviewer {
  id: number;
  name: string;
  email?: string;
  position?: string;
  department?: string;
  status: 'active' | 'inactive';
  notes?: string;
  created_at: string;
}

// ════════════════════════════════════════════
// 统计/仪表盘
// ════════════════════════════════════════════

export interface DashboardStats {
  requests: { total: number; active: number; completed: number; headcount_total?: number; hired_count?: number; remaining_headcount?: number };
  resumes: {
    total: number;
    pending: number;
    ai_pass: number;
    ai_reject: number;
    manual_pass: number;
    manual_reject: number;
    in_pool: number;
  };
  interviews: {
    total: number;
    pending: number;
    confirmed: number;
    completed: number;
    cancelled: number;
    by_round?: Record<string, number>;
  };
  interviewers: { total: number; active: number };
  pipeline: {
    resumes_in_pool?: number;
    interviews_total?: number;
    interviews_completed: number;
    offers_sent: number;
    offers_accepted: number;
    onboarded: number;
  };
}

// ════════════════════════════════════════════
// Offer 管理
// ════════════════════════════════════════════

export type OfferStatus = 'draft' | 'sent' | 'accepted' | 'rejected' | 'withdrawn' | 'onboarded';

export interface Offer {
  id: number;
  resume_id?: number;
  jd_id?: number;
  candidate_name: string;
  position_name: string;
  department: string;
  salary: string;
  equity?: string;
  start_date?: string;
  status: OfferStatus;
  sent_at?: string;
  accepted_at?: string;
  rejected_at?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
}

// ════════════════════════════════════════════
// 入职管理
// ════════════════════════════════════════════

export interface OnboardingItem {
  id: number;
  resume_id?: number;
  candidate_name: string;
  position_name: string;
  department: string;
  salary: string;
  equity?: string;
  start_date?: string;
  accepted_at?: string;
  onboarded_at?: string;
  status: 'pending' | 'completed';
  notes?: string;
}

// ════════════════════════════════════════════
// API 通用
// ════════════════════════════════════════════

export interface ApiError {
  detail: string;
}

// ════════════════════════════════════════════
// 候选人管理
// ════════════════════════════════════════════

export interface EvalSummary {
  round: string;
  round_label: string;
  evaluator?: string;
  tech_score?: number;
  communication_score?: number;
  overall_score?: number;
  strengths?: string;
  weaknesses?: string;
  conclusion?: string;
  recommendation?: string;
  created_at?: string;
}

export interface InterviewSummary {
  id: number;
  round: string;
  round_label: string;
  interviewer_name?: string;
  status: string;
  scheduled_at?: string;
  meeting_link?: string;
  evaluations: EvalSummary[];
}

export interface OfferSummary {
  id: number;
  salary?: string;
  equity?: string;
  status: string;
  start_date?: string;
  sent_at?: string;
  accepted_at?: string;
}

export interface CandidateDetail {
  id: number;
  name?: string;
  email?: string;
  skills?: string;
  experience_years?: number;
  education?: string;
  work_experience?: string;
  ai_score?: number;
  ai_recommended?: boolean;
  ai_reason?: string;
  deep_analysis?: Record<string, unknown>;
  status: string;
  notes?: string;
  jd_title?: string;
  department?: string;
  interviews: InterviewSummary[];
  interviews_total: number;
  best_round?: string;
  avg_score?: number;
  offer?: OfferSummary;
  offer_status?: string;
  created_at?: string;
}

export interface CandidateListResponse {
  total: number;
  items: CandidateDetail[];
}

export interface CandidateStats {
  total_in_pool: number;
  total_interviewed: number;
  offered_count: number;
  onboarded_count: number;
}
