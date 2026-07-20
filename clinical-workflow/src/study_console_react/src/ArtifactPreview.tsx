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
  if (isMappingSpec(preview.value)) {
    return <MappingSpecPreview value={preview.value} />;
  }
  if (isWikiContext(preview.value)) {
    return <WikiContextPreview value={preview.value} />;
  }
  return <pre className="preview-block">{JSON.stringify(preview.value, null, 2)}</pre>;
}

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isMappingSpec(value: unknown): value is JsonObject {
  return isObject(value) && typeof value.spec_id === "string" && Array.isArray(value.mappings);
}

function isWikiContext(value: unknown): value is JsonObject {
  return isObject(value) && value.scope === "p9-poc-test-only" && Array.isArray(value.rules);
}

function objectArray(value: unknown): JsonObject[] {
  return Array.isArray(value) ? value.filter(isObject) : [];
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function MappingSpecPreview({ value }: { value: JsonObject }) {
  const source = isObject(value.source) ? value.source : {};
  const knowledge = isObject(value.knowledge) ? value.knowledge : {};
  const mappings = objectArray(value.mappings);
  const gaps = objectArray(value.explicit_gaps);
  return (
    <div className="structured-preview">
      <div className="preview-callout">
        <strong>Mapping 决策</strong>
        <span>源数据只作为 provenance；本表主体是 Source→Target、受控操作和 Wiki 规则。</span>
      </div>
      <dl className="review-facts">
        <div><dt>spec</dt><dd>{display(value.spec_id)}</dd></div>
        <div><dt>status</dt><dd>{display(value.status)}</dd></div>
        <div><dt>target</dt><dd>{display(value.target_dataset)}</dd></div>
        <div><dt>source</dt><dd>{display(source.relative_path)}</dd></div>
        <div><dt>source sha</dt><dd className="mono">{display(source.sha256).slice(0, 12)}…</dd></div>
        <div><dt>wiki snapshot</dt><dd>{display(knowledge.snapshot_id)}</dd></div>
      </dl>
      <div className="table-scroll">
        <table className="evidence-table">
          <thead><tr><th>Target</th><th>Source</th><th>Operation</th><th>Parameters</th><th>Wiki rules</th><th>Review</th></tr></thead>
          <tbody>
            {mappings.map((mapping, index) => (
              <tr key={display(mapping.mapping_id) + index}>
                <td><strong>{display(mapping.target_variable)}</strong></td>
                <td>{stringArray(mapping.source_variables).join(", ") || "—"}</td>
                <td><code>{display(mapping.operation)}</code></td>
                <td>{display(mapping.parameters)}</td>
                <td>{stringArray(mapping.rule_refs).join(", ") || "—"}</td>
                <td>{display(mapping.review_status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section>
        <h4>显式缺口</h4>
        {gaps.length ? (
          <div className="reference-grid">
            {gaps.map((gap, index) => (
              <article key={display(gap.gap_id) + index}>
                <strong>{display(gap.gap_id)}</strong>
                <span>{stringArray(gap.affects_variables).join(", ")}</span>
                <small>{display(gap.description)}</small>
              </article>
            ))}
          </div>
        ) : <div className="empty-state">没有登记显式缺口。</div>}
      </section>
    </div>
  );
}

function WikiContextPreview({ value }: { value: JsonObject }) {
  const snapshot = isObject(value.snapshot) ? value.snapshot : {};
  const release = isObject(value.release) ? value.release : {};
  const rules = objectArray(value.rules);
  return (
    <div className="structured-preview">
      <div className="preview-callout preview-callout-warn">
        <strong>测试用 Wiki Context</strong>
        <span>scope: {display(value.scope)}；production eligible: {display(value.production_eligible)}</span>
      </div>
      <dl className="review-facts">
        <div><dt>snapshot</dt><dd>{display(snapshot.snapshot_id)}</dd></div>
        <div><dt>version</dt><dd>{display(snapshot.version)}</dd></div>
        <div><dt>snapshot sha</dt><dd className="mono">{display(snapshot.sha256).slice(0, 12)}…</dd></div>
        <div><dt>release</dt><dd>{display(release.release_id)}</dd></div>
        <div><dt>source</dt><dd>{display(release.source_id)}</dd></div>
        <div><dt>rules</dt><dd>{rules.length}</dd></div>
      </dl>
      <div className="table-scroll">
        <table className="evidence-table">
          <thead><tr><th>Rule ID</th><th>Statement</th><th>Source</th><th>Locators</th></tr></thead>
          <tbody>
            {rules.map((rule, index) => (
              <tr key={display(rule.rule_id) + index}>
                <td><code>{display(rule.rule_id)}</code></td>
                <td>{display(rule.statement)}</td>
                <td>{display(rule.source_version)}</td>
                <td>{objectArray(rule.locators).map((locator) => display(locator.locator_id)).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
