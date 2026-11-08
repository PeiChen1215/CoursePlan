import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { qk } from "../lib/queryKeys";
import type {
  CapacityResult, Concept, Constraint, DraftDetail, Extraction, PrereqEdge, Progress,
  VersionDiff, VersionRow,
} from "../lib/types";

export interface PlanRow {
  plan_id: number;
  course_id: number;
  status: string;
  current_version: number | null;
  progress_revision: number;
  updated_at: string;
  course_name: string;
}

export interface BoardTask {
  task_id: number;
  concept_id: number;
  concept_name: string;
  kind: "study" | "practice";
  minutes: number;
  start: string;
  end: string;
  done: boolean;
  overdue: boolean;
  issue_codes: string[];
  actual_minutes?: number | null;
  slice_no: number;
  slice_total: number;
}

export interface UnscheduledRow {
  task_id: number;
  concept_id: number;
  concept_name: string;
  kind: "study" | "practice";
  minutes: number;
  reason: string;
}

export interface IssueRow {
  code: string;
  level: "ERROR" | "WARN" | "INFO";
  message: string;
  concept_id?: number | null;
  suggestion: string;
}

export interface BoardData {
  plan_id: number;
  version_no: number | null;
  readonly: boolean;
  tasks: BoardTask[];
  unscheduled: UnscheduledRow[];
  issues: IssueRow[];
  progress: Progress;
}

export function usePlans() {
  return useQuery({
    queryKey: qk.plans,
    queryFn: () => api.get<{ items: PlanRow[] }>("/api/plans"),
  });
}

export function useCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (courseId: number) =>
      api.post<{ plan_id: number; status: string }>("/api/plans", { course_id: courseId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.plans }),
  });
}

export function useBoard(planId: number | null, version?: number) {
  return useQuery({
    queryKey: qk.board(planId ?? 0, version),
    enabled: planId != null,
    queryFn: () =>
      api.get<BoardData>(
        "/api/plans/" + planId + "/board" + (version != null ? "?version=" + version : ""),
      ),
  });
}

export function useConstraint(planId: number | null) {
  return useQuery({
    queryKey: ["constraint", planId],
    enabled: planId != null,
    queryFn: () => api.get<Constraint | null>("/api/plans/" + planId + "/constraint"),
  });
}

export function usePreviewCapacity(planId: number) {
  return useMutation({
    mutationFn: (payload: unknown) =>
      api.post<CapacityResult>("/api/plans/" + planId + "/capacity/preview", payload),
  });
}

export function useSaveConstraint(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: unknown) =>
      api.put<CapacityResult & { constraint_id: number }>(
        "/api/plans/" + planId + "/constraint",
        payload,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["constraint", planId] });
      qc.invalidateQueries({ queryKey: qk.plans });
    },
  });
}

export function useGenerateDraft(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<DraftDetail>("/api/plans/" + planId + "/drafts"),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.plans }),
  });
}

export function useDraft(planId: number | null, revision: number | null) {
  return useQuery({
    queryKey: qk.draft(planId ?? 0, revision ?? 0),
    enabled: planId != null && revision != null,
    queryFn: () => api.get<DraftDetail>("/api/plans/" + planId + "/drafts/" + revision),
  });
}

export function useConfirmDraft(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { revision: number; confirmKey: string }) =>
      api.post<{ version_no: number; replayed: boolean; diff: VersionDiff | null }>(
        "/api/plans/" + planId + "/drafts/" + args.revision + "/confirm",
        { revision: args.revision },
        { "Idempotency-Key": args.confirmKey },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["board", planId] });
      qc.invalidateQueries({ queryKey: qk.versions(planId) });
      qc.invalidateQueries({ queryKey: qk.plans });
    },
  });
}

export function useVersions(planId: number | null) {
  return useQuery({
    queryKey: qk.versions(planId ?? 0),
    enabled: planId != null,
    queryFn: () => api.get<{ items: VersionRow[] }>("/api/plans/" + planId + "/versions"),
  });
}

export function useDiff(planId: number, a: number | null, b: number | null) {
  return useQuery({
    queryKey: qk.diff(planId, a ?? 0, b ?? 0),
    enabled: a != null && b != null && a !== b,
    queryFn: () =>
      api.get<VersionDiff>("/api/plans/" + planId + "/versions/" + a + "/diff?against=" + b),
  });
}

export function useSubmitEvent(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: {
      taskId: number;
      type: "done" | "correction" | "note";
      minutes?: number | null;
      note?: string | null;
      correctsEventId?: number | null;
    }) =>
      api.post<{ event_id: number; replayed: boolean; completion_rate: number }>(
        "/api/plans/" + planId + "/events",
        {
          task_id: args.taskId,
          event_type: args.type,
          actual_minutes: args.minutes ?? null,
          note: args.note ?? null,
          corrects_event_id: args.correctsEventId ?? null,
        },
        { "Idempotency-Key": "ui-" + crypto.randomUUID() },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["board", planId] });
      qc.invalidateQueries({ queryKey: qk.progress(planId) });
    },
  });
}

export function useExtract() {
  return useMutation({
    mutationFn: (args: { utterance: string; filled: Record<string, unknown> }) =>
      api.post<Extraction>("/api/agent/extract", {
        utterance: args.utterance,
        filled: args.filled,
        course_id: 1,
      }),
  });
}

export function useCourses() {
  return useQuery({
    queryKey: qk.courses,
    queryFn: () => api.get<{ items: { course_id: number; name: string; total_hours: number }[] }>(
      "/api/courses",
    ),
  });
}

export function useConcepts(courseId: number | null) {
  return useQuery({
    queryKey: qk.concepts(courseId ?? 0),
    enabled: courseId != null,
    queryFn: () =>
      api.get<{ items: Concept[] }>("/api/courses/" + courseId + "/concepts?include_disabled=true"),
  });
}

export function useCreateConcept(courseId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      name: string;
      chapter: string;
      difficulty: number;
      reference_minutes: number;
    }) => api.post<{ concept_id: number }>("/api/courses/" + courseId + "/concepts", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.concepts(courseId) }),
  });
}

export function usePrereqs(courseId: number | null) {
  return useQuery({
    queryKey: qk.prereqs(courseId ?? 0),
    enabled: courseId != null,
    queryFn: () => api.get<{ items: PrereqEdge[] }>("/api/courses/" + courseId + "/prerequisites"),
  });
}

export function useSubmitPrereqs(courseId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (edges: [number, number][]) =>
      api.post<{ saved: number }>("/api/courses/" + courseId + "/prerequisites/batch", { edges }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.prereqs(courseId) }),
  });
}
