import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  try {
    const token = localStorage.getItem('gate_intelligence_jwt');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    // Ignore storage errors in restricted frames
  }
  return config;
});

export const gateApi = {
  // Questions (Phase 1)
  listQuestions: (params?: {
    paper_code?: string;
    examination_year?: number;
    subject_name?: string;
    topic_name?: string;
    question_type?: string;
    marks?: number;
    q?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.get('/questions', { params }).then((r) => r.data),

  getQuestionDetails: (questionId: string) =>
    apiClient.get(`/questions/${questionId}`).then((r) => r.data),

  checkAnswer: (
    questionId: string,
    payload: { selected_options?: string[]; numerical_answer?: number; time_spent_seconds?: number }
  ) => apiClient.post(`/questions/${questionId}/check`, payload).then((r) => r.data),

  getQuestionAssets: (questionId: string) =>
    apiClient.get(`/questions/${questionId}/assets`).then((r) => r.data),

  getAssetImageUrl: (assetId: string) => `${API_BASE_URL}/assets/${assetId}/image`,

  listSupportedPapers: () =>
    apiClient.get('/taxonomy/papers').then((r) => r.data),

  listSubjects: (paperCode: string = 'CS') =>
    apiClient.get('/taxonomy/subjects', { params: { paper_code: paperCode } }).then((r) => r.data),

  // Dashboard (Phase 2)
  getDashboardMetrics: (paperCode: string = 'CS') =>
    apiClient.get('/dashboard/metrics', { params: { paper_code: paperCode } }).then((r) => r.data),

  getDashboardProgress: (paperCode: string = 'CS') =>
    apiClient.get('/dashboard/progress', { params: { paper_code: paperCode } }).then((r) => r.data),

  getDashboardRecent: (paperCode: string = 'CS', limit: number = 10) =>
    apiClient.get('/dashboard/recent', { params: { paper_code: paperCode, limit } }).then((r) => r.data),

  // Papers (Phase 3)
  listPapers: (params?: { paper_code?: string; examination_year?: number }) =>
    apiClient.get('/papers', { params }).then((r) => r.data),

  getPaperDetails: (paperId: string) =>
    apiClient.get(`/papers/${paperId}`).then((r) => r.data),

  getPaperQuestions: (paperId: string) =>
    apiClient.get(`/papers/${paperId}/questions`).then((r) => r.data),

  uploadPaperPdf: (formData: FormData) =>
    apiClient
      .post('/papers/upload-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data),

  confirmPaperImport: (payload: {
    paper_code: string;
    examination_year: number;
    session_set?: string;
    paper_title?: string;
    file_checksum?: string;
    file_path?: string;
    page_count?: number;
    is_scanned?: boolean;
    overwrite_if_exists?: boolean;
    questions: any[];
  }) => apiClient.post('/papers/confirm-import', payload).then((r) => r.data),

  // Analytics (Phase 4)
  getDistributions: (paperCode: string = 'CS', subjectName?: string) =>
    apiClient.get('/analytics/distributions', { params: { paper_code: paperCode, subject_name: subjectName } }).then((r) => r.data),

  getDifficulty: (paperCode: string = 'CS') =>
    apiClient.get('/analytics/difficulty', { params: { paper_code: paperCode } }).then((r) => r.data),

  // CBT Mock Tests (Phase 5)
  startTest: (payload: {
    paper_code?: string;
    test_mode?: string;
    paper_id?: string;
    year?: number;
    subject_name?: string;
    duration_minutes?: number;
  }) => apiClient.post('/tests/start', payload).then((r) => r.data),

  getTestState: (testId: string) =>
    apiClient.get(`/tests/${testId}`).then((r) => r.data),

  submitTest: (
    testId: string,
    payload: {
      responses: Array<{
        question_id: string;
        selected_options?: string[];
        numerical_answer?: number;
        marked_for_review?: boolean;
        time_spent_seconds?: number;
      }>;
    }
  ) => apiClient.post(`/tests/${testId}/submit`, payload).then((r) => r.data),

  getTestResult: (resultId: string) =>
    apiClient.get(`/tests/results/${resultId}`).then((r) => r.data),

  getTestHistory: (paperCode: string = 'CS') =>
    apiClient.get('/tests/history', { params: { paper_code: paperCode } }).then((r) => r.data),

  // Lightweight Agents (Phase 6)
  runPyqAnalysis: (payload: { paper_code?: string; subject_name?: string }) =>
    apiClient.post('/agents/pyq-analysis', payload).then((r) => r.data),

  runPerformanceAnalysis: (payload: { paper_code?: string }) =>
    apiClient.post('/agents/performance', payload).then((r) => r.data),

  runQuestionAssistant: (payload: { question_id: string }) =>
    apiClient.post('/agents/question-assistant', payload).then((r) => r.data),

  runPaperAnalysis: (payload: { paper_id?: string; year?: number; paper_code?: string }) =>
    apiClient.post('/agents/paper-analysis', payload).then((r) => r.data),

  // Settings & Data Management (Phase 7)
  getSystemInfo: () =>
    apiClient.get('/settings/info').then((r) => r.data),

  getPreferences: () =>
    apiClient.get('/settings/preferences').then((r) => r.data),

  savePreferences: (payload: { theme?: string; default_paper?: string; timer_alert_minutes?: number }) =>
    apiClient.post('/settings/preferences', payload).then((r) => r.data),

  createBackup: () =>
    apiClient.post('/settings/backup').then((r) => r.data),

  resetProgress: (confirm: boolean = true) =>
    apiClient.post('/settings/reset-progress', { confirm }).then((r) => r.data),

  importJsonDataset: (payload: Record<string, any>) =>
    apiClient.post('/settings/import-json', payload).then((r) => r.data),
};
