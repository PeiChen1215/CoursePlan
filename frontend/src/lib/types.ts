export interface LoginResult {
  token: string;
  role: "student" | "admin";
  expires_at: string;
  user_id: number;
}

export interface Me {
  user_id: number;
  username: string;
  role: "student" | "admin";
}

export interface Concept {
  concept_id: number;
  name: string;
  chapter: string;
  difficulty: number;
  reference_minutes: number;
  status: string;
}

export interface PrereqEdge {
  from_concept_id: number;
  to_concept_id: number;
}

export interface CapacityResult {
  C: number;
  B: number;
  C_prime: number;
  slots: number;
  path_minutes: number;
  goals: number[];
  reject_reason?: string | null;
}

export interface Constraint {
  constraint_id: number;
  target_concept_id: number;
  extra_concept_ids: number[];
  deadline: string;
  availability: Record<string, string[][]>;
  excluded_dates: string[];
  mastered_concept_ids: number[];
  base_time: string;
}

export interface TaskItem {
  concept_id: number;
  kind: "study" | "practice";
  minutes: number;
}

export interface SliceItem {
  concept_id: number;
  kind: "study" | "practice";
  slice_no: number;
  start: string;
  end: string;
}

export interface UnscheduledItem {
  concept_id: number;
  kind: "study" | "practice";
  reason: string;
}

export interface Issue {
  code: string;
  level: "ERROR" | "WARN" | "INFO";
  message: string;
  concept_id?: number | null;
  kind?: string | null;
  suggestion: string;
  detail?: unknown;
}

export interface DraftDetail {
  revision: number;
  tasks: TaskItem[];
  slices: SliceItem[];
  unscheduled: UnscheduledItem[];
  metrics: {
    total_minutes: number;
    raw_minutes: number;
    buffer_minutes: number;
    usable_minutes: number;
    deficit_minutes: number;
    utilization: number;
    scheduled_minutes: number;
    slices: number;
  };
  report: { passed: boolean; issues: Issue[] };
}

export interface VersionRow {
  version_no: number;
  version_id: number;
  change_reason: string;
  change_note: string;
  created_at: string;
  input_hash: string;
  tasks: number;
  slices: number;
}

export interface VersionDiff {
  added: number[];
  removed: number[];
  moved: number[];
  resized: number[];
}

export interface Progress {
  total_tasks: number;
  done_tasks: number;
  completion_rate: number;
  planned_minutes: number;
  actual_minutes: number;
  overdue_tasks: number[];
}

export interface Extraction {
  fields: {
    target_concept_id?: number;
    deadline?: string;
    availability?: Record<string, string[][]>;
    daily_limit?: number;
    [key: string]: unknown;
  };
  questions: string[];
  candidates: { concept_id: number; name: string }[];
  mode: "local" | "mock" | "llm";
  degraded_reason?: string | null;
  warnings: string[];
}

export interface BoardTask {
  taskId: number;
  conceptId: number;
  conceptName: string;
  kind: "study" | "practice";
  minutes: number;
  start: string;
  end: string;
  done: boolean;
  overdue: boolean;
  issueCodes: string[];
}
