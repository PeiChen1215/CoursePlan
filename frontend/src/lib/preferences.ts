export type BoardView = "today" | "week" | "all";
export const BOARD_VIEW_KEY = "studypath.board-view";

export function readPreference(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

export function savePreference(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* Preferences remain usable without storage. */ }
}

export function readBoardView(): BoardView {
  const saved = readPreference(BOARD_VIEW_KEY);
  return saved === "week" || saved === "all" ? saved : "today";
}
