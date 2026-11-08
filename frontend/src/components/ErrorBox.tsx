import { ApiError } from "../lib/api";

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className="sheet sheet-pad" style={{ borderColor: "var(--crimson)" }}>
      <p className="display text-sm" style={{ color: "var(--crimson)" }}>
        {apiError ? apiError.code : "请求失败"}
      </p>
      <p className="muted mt-1 text-sm">{apiError ? apiError.message : String(error)}</p>
      {apiError?.field ? <p className="faint mt-1 text-xs">字段：{apiError.field}</p> : null}
      {apiError?.detail && typeof apiError.detail === "object" ? (
        <pre className="faint mt-2 overflow-x-auto text-xs">
          {JSON.stringify(apiError.detail, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
