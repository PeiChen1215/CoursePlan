import { ApiError } from "../lib/api";

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className="rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800">
      <p className="font-medium">{apiError ? apiError.code : "请求失败"}</p>
      <p>{apiError ? apiError.message : String(error)}</p>
      {apiError?.field ? <p className="text-xs">字段：{apiError.field}</p> : null}
      {apiError?.detail && typeof apiError.detail === "object" ? (
        <pre className="mt-1 overflow-x-auto text-xs opacity-80">
          {JSON.stringify(apiError.detail, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
