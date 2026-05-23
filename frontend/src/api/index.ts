import axios from 'axios';
import type {
  JobDescription, Resume, ResumeListResponse,
  Interview, InterviewCreatePayload, PipelineResponse,
  Interviewer, DashboardStats,
  Offer, OnboardingItem,
  CandidateListResponse, CandidateDetail, CandidateStats,
} from '../types';

const http = axios.create({ baseURL: '/api' });

// ─── 工具：泛型提取响应数据 ───
function extract<T>(promise: Promise<{ data: T }>): Promise<T> {
  return promise.then(r => r.data);
}

// ─── 工作流 ───
export const startWorkflow = (data: Record<string, unknown>) =>
  extract<Record<string, unknown>>(http.post('/workflow/start', data));

export const getWorkflowState = (id: number) =>
  extract<Record<string, unknown>>(http.get(`/workflow/${id}/state`));

export const workflowAction = (requestId: number, action: string, data?: Record<string, unknown>) =>
  extract<Record<string, unknown>>(http.post('/workflow/action', { request_id: requestId, action, data }));

export const listActiveWorkflows = () =>
  extract<unknown[]>(http.get('/workflow/active'));

export const getGraphDefinition = () =>
  extract<Record<string, unknown>>(http.get('/workflow/graph-definition'));

// ─── JD 审查 & 管理 ───
export const listPendingJDs = () =>
  extract<JobDescription[]>(http.get('/workflow/pending-jds'));

export const approvePendingJD = (jdId: number) =>
  extract<JobDescription>(http.post(`/workflow/approve-jd/${jdId}`));

export const rejectPendingJD = (jdId: number, reason?: string) =>
  extract<Record<string, unknown>>(http.post(`/workflow/reject-jd/${jdId}?reason=${encodeURIComponent(reason || '')}`));

export const regenerateJD = (jdId: number, modificationHints: string) =>
  extract<JobDescription>(http.post(`/jds/${jdId}/regenerate`, { modification_hints: modificationHints }));

export const saveJDContent = (jdId: number, content: string) =>
  extract<Record<string, unknown>>(http.put(`/jds/${jdId}/content`, { content }));

export const listApprovedJDs = () =>
  extract<JobDescription[]>(http.get('/workflow/approved-jds'));

export const enhanceJD = (jdId: number, context?: string) =>
  extract<Record<string, unknown>>(http.post('/jds/enhance', { jd_id: jdId, additional_context: context || '' }));

export const reviewJD = (jdId: number, approved: boolean, comment?: string) =>
  extract<Record<string, unknown>>(http.post(`/jds/${jdId}/review`, { jd_id: jdId, approved, review_comment: comment || '' }));

// ─── 简历筛选工作流 ───
export const startScreeningWorkflow = (requestId: number) =>
  extract<Record<string, unknown>>(http.post('/workflow/start-screening', null, { params: { request_id: requestId } }));

// ─── 简历 ───
export const uploadResume = (file: File, jdId?: number) => {
  const fd = new FormData();
  fd.append('file', file);
  if (jdId) fd.append('jd_id', String(jdId));
  return extract<Resume & { processing?: boolean }>(http.post('/resumes/upload', fd));
};

export const listResumes = (params?: Record<string, unknown>) =>
  extract<ResumeListResponse>(http.get('/resumes', { params }));

export const deepAnalyze = (resumeId: number, jdId?: number) =>
  extract<Record<string, unknown>>(http.post(`/resumes/${resumeId}/deep-analyze`, { jd_id: jdId }));

export const batchAction = (data: { resume_ids: number[]; action: string }) =>
  extract<Record<string, unknown>>(http.post('/resumes/batch-action', data));

export const updateResumeJD = (resumeId: number, jdId: number | null) =>
  extract<Resume>(http.patch(`/resumes/${resumeId}/jd`, { jd_id: jdId }));

// ─── 面试 ───
export const listInterviews = (params?: Record<string, unknown>) =>
  extract<Interview[]>(http.get('/interviews', { params }));

export const createInterview = (data: InterviewCreatePayload) =>
  extract<Interview>(http.post('/interviews', data));

export const generateQuestions = (interviewId: number) =>
  extract<unknown[]>(http.post(`/interviews/${interviewId}/questions`));

export const evaluateInterview = (interviewId: number, data: Record<string, unknown>) =>
  extract<Record<string, unknown>>(http.post(`/interviews/${interviewId}/evaluate`, data));

// ─── 删除操作 ───
export const deleteWorkflow = (requestId: number) =>
  extract<Record<string, unknown>>(http.delete(`/workflow/${requestId}`));

export const deleteJD = (jdId: number) =>
  extract<Record<string, unknown>>(http.delete(`/jds/${jdId}`));

export const deleteResume = (resumeId: number) =>
  extract<Record<string, unknown>>(http.delete(`/resumes/${resumeId}`));

export const updateResumeNotes = (resumeId: number, notes: string) =>
  extract<{ id: number; notes: string }>(http.patch(`/resumes/${resumeId}/notes`, { notes }));

export const deleteInterview = (id: number) =>
  extract<Record<string, unknown>>(http.delete(`/interviews/${id}`));

// ─── 面试官库 ───
export const listInterviewers = (params?: Record<string, unknown>) =>
  extract<Interviewer[]>(http.get('/interviewers', { params }));

export const getInterviewer = (id: number) =>
  extract<Interviewer>(http.get(`/interviewers/${id}`));

export const createInterviewer = (data: Partial<Interviewer>) =>
  extract<Interviewer>(http.post('/interviewers', data));

export const updateInterviewer = (id: number, data: Partial<Interviewer>) =>
  extract<Interviewer>(http.put(`/interviewers/${id}`, data));

export const deleteInterviewer = (id: number) =>
  extract<Record<string, unknown>>(http.delete(`/interviewers/${id}`));

export const toggleInterviewerStatus = (id: number) =>
  extract<Interviewer>(http.post(`/interviewers/${id}/toggle-status`));

// ═══════════════════════════════════════════
// Offer 管理
// ═══════════════════════════════════════════

export const createOffer = (data: Partial<Offer>) =>
  extract<Offer>(http.post('/offers', data));

export const listOffers = (params?: Record<string, unknown>) =>
  extract<Offer[]>(http.get('/offers', { params }));

export const getOffer = (id: number) =>
  extract<Offer>(http.get(`/offers/${id}`));

export const sendOffer = (id: number, startDate?: string) =>
  extract<Offer>(http.post(`/offers/${id}/send`, { start_date: startDate || null }));

export const acceptOffer = (id: number, startDate?: string) =>
  extract<Offer>(http.post(`/offers/${id}/accept`, { accepted_start_date: startDate || null }));

export const rejectOffer = (id: number, reason?: string) =>
  extract<Offer>(http.post(`/offers/${id}/reject`, { reject_reason: reason || null }));

export const withdrawOffer = (id: number) =>
  extract<Offer>(http.post(`/offers/${id}/withdraw`));

export const deleteOffer = (id: number) =>
  extract<Record<string, unknown>>(http.delete(`/offers/${id}`));

// ═══════════════════════════════════════════
// 入职管理
// ═══════════════════════════════════════════

export const listPendingOnboarding = () =>
  extract<OnboardingItem[]>(http.get('/onboarding/pending'));

export const listCompletedOnboarding = () =>
  extract<OnboardingItem[]>(http.get('/onboarding/completed'));

export const completeOnboarding = (offerId: number, data?: { actual_start_date?: string; notes?: string }) =>
  extract<Record<string, unknown>>(http.post(`/onboarding/${offerId}/complete`, data || {}));

export const deleteOnboarding = (offerId: number) =>
  extract<Record<string, unknown>>(http.delete(`/onboarding/${offerId}`));

// ═══════════════════════════════════════════
// 候选人管理
// ═══════════════════════════════════════════

export const listCandidates = (params?: Record<string, unknown>) =>
  extract<CandidateListResponse>(http.get('/candidates', { params }));

export const getCandidateDetail = (id: number) =>
  extract<CandidateDetail>(http.get(`/candidates/${id}`));

export const getCandidateStats = () =>
  extract<CandidateStats>(http.get('/candidates/stats/summary'));

export const deleteCandidate = (id: number) =>
  extract<Record<string, unknown>>(http.delete(`/candidates/${id}`));

// ═══════════════════════════════════════════
// LangGraph resume
// ═══════════════════════════════════════════
export const resumeWorkflow = (requestId: number, answers: unknown[]) =>
  extract<Record<string, unknown>>(http.post('/workflow/resume', { request_id: requestId, answers }));

// ─── 统计/仪表盘 ───
export const getDashboardStats = () =>
  extract<DashboardStats>(http.get('/stats'));

export default http;
