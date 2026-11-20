export type QuestionType = 'MCQ' | 'MSQ' | 'NAT';
export type AnswerProvenance = 'official_key' | 'manually_verified' | 'ai_generated' | 'unverified';

export interface GatePaperInfo {
  code: string;
  name: string;
  category: string;
  active_from: number;
  active_to: number | null;
  ga_marks: number;
  eng_math_marks: number;
  subject_marks: number;
  allowed_second_papers: string[];
  notes?: string;
}

export interface QuestionOption {
  id?: string;
  option_label: string;
  option_text: string;
  is_correct?: boolean | null;
}

export interface AnswerKey {
  id?: string;
  answer_type: QuestionType;
  correct_options: string[];
  numerical_min?: number | null;
  numerical_max?: number | null;
  tolerance: number;
  provenance: AnswerProvenance;
  explanation?: string | null;
}

export interface VisualAsset {
  id: string;
  question_id: string;
  asset_role: 'stem' | 'option' | 'full_page';
  asset_type: string;
  option_label?: string | null;
  relative_path: string;
  source_page: number;
  bbox_json: string;
  confidence?: number;
  review_status: 'pending' | 'approved' | 'rejected';
}

export interface QuestionItem {
  id: string;
  question_paper_id?: string;
  paper_code: string;
  examination_year: number;
  question_number: number;
  question_type: QuestionType;
  question_text: string;
  math_expressions: string[];
  has_diagram_or_table: boolean;
  marks: number;
  negative_marks: number;
  page_number: number;
  subject_name: string;
  primary_topic_name: string;
  subtopic_name?: string;
  difficulty_level: 'Easy' | 'Medium' | 'Hard';
  syllabus_version_tag: string;
  extraction_confidence: number;
  classification_confidence: number;
  needs_human_review: boolean;
  is_verified: boolean;
  is_ai_generated: boolean;
  options: QuestionOption[];
  visual_assets?: VisualAsset[];
  answer_key?: AnswerKey | null;
}

export interface UploadedPaper {
  id: string;
  paper_code: string;
  examination_year: number;
  session_set: string;
  title: string;
  filename: string;
  file_checksum: string;
  page_count: number;
  is_scanned: boolean;
  processing_status: string;
  total_extracted_questions: number;
  latest_job_id?: string;
  progress_percent?: number;
  current_stage?: string;
  created_at: string;
}

export interface TopicImportanceRow {
  rank: number;
  subject_name: string;
  topic_name: string;
  question_count: number;
  total_marks: number;
  average_marks_per_question: number;
  marks_share_percent: number;
  years_appeared_count: number;
  total_years_in_corpus: number;
  appearance_percentage: number;
  most_recent_year: number;
  years_appeared: number[];
  importance_score: number;
  score_components: {
    normalized_frequency: number;
    normalized_marks_contribution: number;
    year_recurrence_rate: number;
    recency_factor: number;
  };
  explanation: string;
}

export interface BacktestValidation {
  holdout_year: number;
  training_years: number[];
  top_k_evaluated: number;
  predicted_top_k_topics: string[];
  actual_holdout_topics: string[];
  matched_top_k_topics: string[];
  top_k_topic_hit_rate_percent: number;
  holdout_marks_coverage_percent: number;
  validation_note: string;
}

export interface AgentRunRecord {
  id: string;
  workflow_id: string;
  agent_name: string;
  status: string;
  input_summary: string;
  output_summary: string;
  prompt_tokens: number;
  completion_tokens: number;
  duration_ms: number;
  error_message?: string | null;
  created_at: string;
}
