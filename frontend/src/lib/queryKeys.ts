export const qk = {
  me: ["me"] as const,
  plans: ["plans"] as const,
  board: (planId: number, version?: number) => ["board", planId, version ?? "current"] as const,
  draft: (planId: number, revision: number) => ["draft", planId, revision] as const,
  versions: (planId: number) => ["versions", planId] as const,
  diff: (planId: number, a: number, b: number) => ["diff", planId, a, b] as const,
  progress: (planId: number) => ["progress", planId] as const,
  courses: ["courses"] as const,
  concepts: (courseId: number) => ["concepts", courseId] as const,
  prereqs: (courseId: number) => ["prereqs", courseId] as const,
};
