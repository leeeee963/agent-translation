/** Matches backend config/settings.yaml supported_languages entries */
export interface Language {
  code: string;
  name: string;
}

/** A file queued for upload in the UI */
export interface TranslationFile {
  id: string;
  name: string;
  size: number;
  file: File; // the raw File object for FormData
  uploadProgress?: number;
  uploadStatus?: 'pending' | 'uploading' | 'completed' | 'error';
}

/** A single block rewritten by the naturalness review pass */
export interface ReviewChange {
  block_id: string;
  source_text: string;
  before: string;
  after: string;
  changed?: boolean;
}

/** Backend language run status (from TranslationTask model) */
export interface LanguageRun {
  target_language: string;
  status: string;
  stage: string;
  detail: string;
  percent: number;
  segments_done: number;
  segments_total: number;
  units_done: number;
  units_total: number;
  unit_label: string;
  current_range: string;
  output_file: string;
  download_url: string;
  draft_download_url?: string;
  error_message: string;
  review_changes?: ReviewChange[];
}

/** Backend glossary exports shape */
export interface GlossaryExports {
  columns?: string[];
  rows?: Record<string, string>[];
}

/** Glossary term with strategy and review fields */
export interface GlossaryTerm {
  id: string;
  source: string;
  targets: Record<string, string>;
  category: string;
  context: string;
  do_not_translate: boolean;
  confirmed: boolean;
  frequency: number;
  strategy: "hard" | "keep_original" | "skip";
  ai_category: string;
  uncertain: boolean;
  uncertainty_note: string;
  library_term_id: number | null;
  save_to_library: boolean;
}

/** Terminology library domain */
export interface LibraryDomain {
  id: number;
  name: string;
  name_en: string;
  name_zh: string;
  description: string;
  description_zh: string;
  term_count: number;
  created_at: string;
  updated_at: string;
}

/** Terminology library term */
export interface LibraryTerm {
  id: number;
  domain_id: number;
  source: string;
  targets: Record<string, string>;
  strategy: "hard" | "keep_original" | "skip";
  ai_category: string;
  context: string;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  use_count: number;
}

/** Backend glossary shape */
export interface GlossaryData {
  glossary_id: string;
  source_language: string;
  target_languages: string[];
  source_file: string;
  terms: GlossaryTerm[];
  confirmed: boolean;
}

/** Job status union */
export type JobStatus =
  | "queued"
  | "pending"
  | "parsing"
  | "terminology"
  | "awaiting_glossary_review"
  | "translating"
  | "reviewing"
  | "rebuilding"
  | "done"
  | "error"
  | "cancelled";

/** Backend job shape (from JobQueue / TranslationJob model) */
export interface Job {
  job_id: string;
  filename: string;
  source_file: string;
  source_language: string;
  use_glossary: boolean;
  status: JobStatus;
  stage: string;
  detail: string;
  percent: number;
  segments_done: number;
  segments_total: number;
  units_done: number;
  units_total: number;
  unit_label: string;
  current_range: string;
  target_languages: string[];
  glossary: GlossaryData | null;
  glossary_exports: GlossaryExports;
  language_runs: LanguageRun[];
  result: unknown;
  error: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

/** UI-level translation task (mapped from backend Job language_runs) */
export interface TranslationTask {
  id: string;
  language: Language;
  status: 'pending' | 'extracting' | 'translating' | 'completed' | 'error';
  progress: number;
  currentRange?: string;
  downloadUrl?: string;
  errorMessage?: string;
}
