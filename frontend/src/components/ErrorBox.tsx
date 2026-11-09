import { ApiError } from "../lib/api";
import { Card } from "./ui";

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div role="alert" aria-live="assertive">
      <Card className="card-pad" quiet>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <span className="chip" data-tone="danger">
            {apiError ? apiError.code : "请求失败"}
          </span>
          <div style={{ flex: 1 }}>
            <p className="h3">{apiError ? apiError.message : String(error)}</p>
            {apiError?.field ? <p className="row-sub">字段：{apiError.field}</p> : null}
            {apiError?.detail && typeof apiError.detail === "object" ? (
              <pre
                className="mono-sm"
                style={{ marginTop: 6, overflowX: "auto", whiteSpace: "pre-wrap" }}
              >
                {JSON.stringify(apiError.detail, null, 2)}
              </pre>
            ) : null}
          </div>
        </div>
      </Card>
    </div>
  );
}
