import { useQuery } from "@tanstack/react-query";

import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { getJson } from "../api/client";
import {
  API_PATHS,
  type AuditEvent,
  type AuditEventCollection,
  type AuditVersion,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

export interface AuditSearch {
  actor: string;
  action: string;
  objectType: string;
  result: string;
  cursor: string;
  event: string;
}

interface AuditPageProps {
  search: AuditSearch;
  onSearchChange: (patch: Partial<AuditSearch>) => void;
}

function auditPath(search: AuditSearch): string {
  const params = new URLSearchParams({ limit: "25" });
  if (search.actor) params.set("actor", search.actor);
  if (search.action) params.set("action", search.action);
  if (search.objectType) params.set("object_type", search.objectType);
  if (search.result) params.set("result", search.result);
  if (search.cursor) params.set("cursor", search.cursor);
  return `${API_PATHS.auditEvents}?${params.toString()}`;
}

export function AuditPage({ search, onSearchChange }: AuditPageProps) {
  useDocumentTitle("审计记录");
  const events = useQuery({
    queryKey: [
      "audit-events",
      search.actor,
      search.action,
      search.objectType,
      search.result,
      search.cursor,
    ],
    queryFn: ({ signal }) =>
      getJson<AuditEventCollection>(auditPath(search), signal),
    staleTime: 10_000,
  });
  const items = events.data?.data.items ?? [];
  const selected =
    items.find((event) => event.auditEventId === search.event) ?? items[0];

  const updateFilter = (patch: Partial<AuditSearch>) => {
    onSearchChange({
      ...patch,
      cursor: "",
      event: "",
    });
  };

  return (
    <section className={styles.page} aria-labelledby="audit-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>KUI-10 / 只追加治理账本</p>
          <h1 className={styles.title} id="audit-title">
            审计记录
          </h1>
          <p className={styles.lede}>
            只读查看操作者、动作、对象、版本事实、结果与关联 ID。原始
            详情、凭据和敏感正文不会返回浏览器。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>排序</span>
          <span className={styles.asideValue}>最新优先 · 不可变</span>
        </div>
      </header>

      <div className={styles.auditFilters}>
        <FilterField
          label="操作者"
          value={search.actor}
          placeholder="usr-review"
          onChange={(actor) => updateFilter({ actor })}
        />
        <FilterField
          label="动作"
          value={search.action}
          placeholder="approved"
          onChange={(action) => updateFilter({ action })}
        />
        <FilterField
          label="对象类型"
          value={search.objectType}
          placeholder="knowledge_revision"
          onChange={(objectType) => updateFilter({ objectType })}
        />
        <FilterField
          label="结果"
          value={search.result}
          placeholder="succeeded"
          onChange={(result) => updateFilter({ result })}
        />
        <button
          className={styles.secondaryButton}
          type="button"
          onClick={() =>
            onSearchChange({
              actor: "",
              action: "",
              objectType: "",
              result: "",
              cursor: "",
              event: "",
            })
          }
        >
          清除筛选
        </button>
      </div>

      <div className={styles.auditFacts} aria-label="审计响应事实">
        <span>
          每页 <b>25</b>
        </span>
        <span>
          返回 <b>{items.length}</b> / {events.data?.data.total ?? 0}
        </span>
        <span>
          快照 <b>{formatTime(events.data?.meta.generatedAt)}</b>
        </span>
        <span>
          延迟 <b>客户端未断言</b>
        </span>
      </div>

      {events.data?.data.partial ? (
        <div className={styles.notice} role="status">
          <span aria-hidden="true">△</span>
          <span>
            {events.data.data.warnings.join("；") || "审计页为部分结果。"}
          </span>
        </div>
      ) : null}

      <div className={styles.auditWorkbench}>
        <div className={styles.auditList} aria-label="审计事件">
          {events.isPending ? <AuditSkeleton /> : null}
          {events.isError ? (
            <CompactAuditState
              title="无法读取审计账本"
              text="权限或 API 失败已显式保留；页面不会回退到本地假数据。"
              error
            />
          ) : null}
          {events.isSuccess && items.length === 0 ? (
            <CompactAuditState
              title="没有匹配事件"
              text="调整 actor、action、object type 或 result。"
            />
          ) : null}
          {items.map((event) => (
            <button
              key={event.auditEventId}
              type="button"
              className={`${styles.auditPicker} ${
                selected?.auditEventId === event.auditEventId
                  ? styles.auditPickerSelected
                  : ""
              }`}
              onClick={() => onSearchChange({ event: event.auditEventId })}
            >
              <span className={styles.auditPickerTop}>
                <strong>{event.action}</strong>
                <time dateTime={event.createdAt}>{formatTime(event.createdAt)}</time>
              </span>
              <span>{event.actorId}</span>
              <small>
                {event.objectType} · {event.objectId}
              </small>
              <span className={styles.status}>{event.result ?? "无结果"}</span>
            </button>
          ))}
          <div className={styles.auditPagination}>
            <button
              className={styles.secondaryButton}
              type="button"
              disabled={!search.cursor}
              onClick={() => onSearchChange({ cursor: "", event: "" })}
            >
              回到最新
            </button>
            <button
              className={styles.secondaryButton}
              type="button"
              disabled={!events.data?.data.nextCursor}
              onClick={() =>
                onSearchChange({
                  cursor: events.data?.data.nextCursor ?? "",
                  event: "",
                })
              }
            >
              下一页
            </button>
          </div>
        </div>

        <div className={styles.auditDetail}>
          {selected ? (
            <AuditEventDetail event={selected} />
          ) : (
            <div className={styles.detailState}>
              <span className={styles.stateSymbol} aria-hidden="true">
                ≡
              </span>
              <h2 className={styles.stateTitle}>选择一个审计事件</h2>
              <p className={styles.stateText}>详情保持只读且只显示安全投影。</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function FilterField({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span className={styles.asideLabel}>{label}</span>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function AuditEventDetail({ event }: { event: AuditEvent }) {
  return (
    <article className={styles.auditPaper}>
      <header>
        <div>
          <span className={styles.eyebrow}>审计事件</span>
          <h2>{event.action}</h2>
        </div>
        <span className={styles.status}>{event.result ?? "无结果"}</span>
      </header>
      <dl className={styles.auditDefinition}>
        <Fact label="事件 ID" value={event.auditEventId} />
        <Fact label="操作者" value={event.actorId} />
        <Fact label="对象" value={`${event.objectType} / ${event.objectId}`} />
        <Fact label="关联任务" value={event.runId ?? "未关联"} />
        <Fact label="关联 ID" value={event.correlationId ?? "未记录"} />
        <Fact label="时间" value={formatTime(event.createdAt)} />
      </dl>
      <div className={styles.versionCompare}>
        <VersionCard title="变更前事实" version={event.beforeVersion} />
        <span aria-hidden="true">→</span>
        <VersionCard title="变更后事实" version={event.afterVersion} />
      </div>
      <p className={styles.readOnlyNote}>
        此为只追加投影，不提供编辑、删除或读取原始详情的操作。
      </p>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function VersionCard({
  title,
  version,
}: {
  title: string;
  version: AuditVersion | null;
}) {
  return (
    <div>
      <span className={styles.asideLabel}>{title}</span>
      {version ? (
        <>
          <strong>
            修订 {version.revisionNumber ?? "未记录"}
          </strong>
          <code title={version.contentSha256 ?? undefined}>
            {version.contentSha256
              ? `sha256:${version.contentSha256.slice(0, 16)}`
                : "哈希未记录"}
          </code>
        </>
      ) : (
        <strong>未记录</strong>
      )}
    </div>
  );
}

function formatTime(value: string | undefined): string {
  if (!value) return "待生成";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "medium",
    hour12: false,
  }).format(new Date(value));
}

function CompactAuditState({
  title,
  text,
  error = false,
}: {
  title: string;
  text: string;
  error?: boolean;
}) {
  return (
    <div className={`${styles.compactState} ${error ? styles.error : ""}`}>
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function AuditSkeleton() {
  return (
    <>
      {[0, 1, 2].map((item) => (
        <div className={styles.auditPicker} key={item}>
          <span className={styles.skeleton} />
          <span className={styles.skeleton} />
        </div>
      ))}
    </>
  );
}
