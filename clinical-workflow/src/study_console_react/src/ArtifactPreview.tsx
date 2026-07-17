import { useEffect, useState } from "react";

import { getArtifactDetail } from "./api";
import type { ArtifactDetail, ArtifactPreviewPayload } from "./types";

export function ArtifactPreview({
  artifactId,
  studyId,
}: {
  artifactId: string | null;
  studyId: string;
}) {
  const [detail, setDetail] = useState<ArtifactDetail | null>(null);
  const [loadState, setLoadState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!artifactId) {
      setDetail(null);
      setLoadState("idle");
      setMessage("");
      return;
    }
    const currentArtifactId = artifactId;
    let cancelled = false;
    async function loadArtifact() {
      setLoadState("loading");
      setMessage("");
      try {
        const payload = await getArtifactDetail(studyId, currentArtifactId);
        if (!cancelled) {
          setDetail(payload);
          setLoadState("ready");
        }
      } catch (error) {
        if (!cancelled) {
          setLoadState("error");
          setMessage(error instanceof Error ? error.message : String(error));
        }
      }
    }
    void loadArtifact();
    return () => {
      cancelled = true;
    };
  }, [artifactId, studyId]);

  if (!artifactId) {
    return <div className="empty-state">选择一个 artifact ref 后显示安全预览。</div>;
  }

  if (loadState === "loading") {
    return <div className="notice">正在读取 artifact preview…</div>;
  }

  if (loadState === "error") {
    return <div className="notice notice-error">{message}</div>;
  }

  if (!detail) {
    return <div className="empty-state">暂无 artifact preview。</div>;
  }

  return (
    <section className="artifact-preview" aria-labelledby="artifact-preview-title">
      <div className="review-form-header">
        <div>
          <p className="eyebrow">UI-06 · Artifact Preview</p>
          <h4 id="artifact-preview-title">{detail.artifact.display_name}</h4>
        </div>
        <span className="status-pill status-muted">{detail.preview?.kind ?? "no-preview"}</span>
      </div>
      <dl className="review-facts">
        <div>
          <dt>relative path</dt>
          <dd>{detail.registered_ref.relative_path}</dd>
        </div>
        <div>
          <dt>sha256</dt>
          <dd className="mono">{detail.registered_ref.sha256.slice(0, 12)}…</dd>
        </div>
        <div>
          <dt>state</dt>
          <dd>{detail.artifact.artifact_state}</dd>
        </div>
      </dl>
      <PreviewBody preview={detail.preview} />
    </section>
  );
}

function PreviewBody({ preview }: { preview: ArtifactPreviewPayload | null }) {
  if (!preview) {
    return <div className="empty-state">该 artifact 没有可用预览。</div>;
  }
  if (preview.kind === "csv") {
    const columns = Object.keys(preview.rows[0] ?? {});
    return (
      <div className="csv-preview">
        <p className="help-text">row_count: {preview.row_count}; showing first {preview.rows.length} rows.</p>
        {columns.length ? (
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row, index) => (
                <tr key={`${index}-${JSON.stringify(row)}`}>
                  {columns.map((column) => (
                    <td key={column}>{row[column]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">CSV preview 无行数据。</div>
        )}
      </div>
    );
  }
  if (preview.kind === "text") {
    return <pre className="preview-block">{preview.value}</pre>;
  }
  return <pre className="preview-block">{JSON.stringify(preview.value, null, 2)}</pre>;
}
