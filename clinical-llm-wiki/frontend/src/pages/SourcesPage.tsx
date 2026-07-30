import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";

import { getJson } from "../api/client";
import {
  API_PATHS,
  type SourceCollection,
  type SourceSummary,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

const columnHelper = createColumnHelper<SourceSummary>();

const columns = [
  columnHelper.accessor("title", {
    header: "Registered source",
    cell: (info) => (
      <span>
        <span className={styles.primary}>{info.getValue()}</span>
        <span className={styles.secondary}>{info.row.original.sourceId}</span>
      </span>
    ),
  }),
  columnHelper.accessor("version", {
    header: "Version",
    cell: (info) => <span className={styles.mono}>{info.getValue()}</span>,
  }),
  columnHelper.accessor("mediaType", {
    header: "Media",
    cell: (info) => <span className={styles.mono}>{info.getValue()}</span>,
  }),
  columnHelper.accessor("rights", {
    header: "Rights",
    cell: (info) => <span className={styles.mono}>{info.getValue()}</span>,
  }),
  columnHelper.accessor("status", {
    header: "Lifecycle",
    cell: (info) => (
      <span
        className={`${styles.status} ${styles[`status${capitalize(info.getValue())}`] ?? ""}`}
      >
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor("sourceHash", {
    header: "Source hash",
    cell: (info) => (
      <span className={styles.mono} title={`sha256:${info.getValue()}`}>
        sha256:{info.getValue().slice(0, 12)}
      </span>
    ),
  }),
];

function capitalize(value: string): string {
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}

interface SourcesPageProps {
  query: string;
  onQueryChange: (query: string) => void;
}

export function SourcesPage({ query, onQueryChange }: SourcesPageProps) {
  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: ({ signal }) => getJson<SourceCollection>(API_PATHS.sources, signal),
    staleTime: 30_000,
  });

  const filtered = useMemo(() => {
    const items = sources.data?.data.items ?? [];
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) {
      return items;
    }
    return items.filter((source) =>
      [source.title, source.sourceId, source.version, source.rights, source.status]
        .join(" ")
        .toLocaleLowerCase()
        .includes(needle),
    );
  }, [query, sources.data?.data.items]);

  const table = useReactTable({
    data: filtered,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <section className={styles.page} aria-labelledby="sources-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Source registry / canonical accession</p>
          <h1 className={styles.title} id="sources-title">
            Sources
          </h1>
          <p className={styles.lede}>
            登记来源、版本、rights 和 source hash。上传只产生 SourceVersion，不直接产生知识。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>Authority</span>
          <span className={styles.asideValue}>Knowledge API</span>
        </div>
      </header>

      <div className={styles.toolbar}>
        <label>
          <span className={styles.asideLabel}>Filter registered sources</span>
          <input
            className={styles.search}
            type="search"
            value={query}
            placeholder="标题、版本、状态或 source ID"
            onChange={(event) => onQueryChange(event.target.value)}
          />
        </label>
        <span className={styles.count} aria-live="polite">
          {sources.isPending ? "loading" : `${filtered.length} / ${sources.data?.data.total ?? 0}`}
        </span>
      </div>

      <div className={styles.panel}>
        {sources.data?.data.partial ? (
          <div className={styles.notice} role="status">
            <span aria-hidden="true">△</span>
            <span>{sources.data.data.warnings.join("；") || "来源列表为部分数据。"}</span>
          </div>
        ) : null}

        {sources.isPending ? <LoadingTable /> : null}
        {sources.isError ? (
          <StatePanel
            symbol="!"
            title="无法读取来源登记"
            text="Knowledge API 未返回可验证的 SourceCollection。页面不会使用本地文件名补齐结果。"
            error
          />
        ) : null}
        {sources.isSuccess && filtered.length === 0 ? (
          <StatePanel
            symbol="∅"
            title={query ? "没有匹配来源" : "尚未登记来源"}
            text={
              query
                ? "清除筛选条件，或使用 source ID、版本和 rights 重新搜索。"
                : "Source Registry 为空；登记来源后仍需独立处理和治理。"
            }
          />
        ) : null}
        {sources.isSuccess && filtered.length > 0 ? (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th key={header.id}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function LoadingTable() {
  return (
    <div className={styles.tableWrap} aria-label="正在加载来源" aria-busy="true">
      <table className={styles.table}>
        <thead>
          <tr>
            {["Registered source", "Version", "Media", "Rights", "Lifecycle", "Source hash"].map(
              (header) => (
                <th key={header}>{header}</th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {[0, 1, 2].map((row) => (
            <tr key={row}>
              {[0, 1, 2, 3, 4, 5].map((cell) => (
                <td key={cell}>
                  <span className={styles.skeleton} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface StatePanelProps {
  symbol: string;
  title: string;
  text: string;
  error?: boolean;
}

function StatePanel({ symbol, title, text, error = false }: StatePanelProps) {
  return (
    <div className={`${styles.statePanel} ${error ? styles.error : ""}`} role="status">
      <div>
        <span className={styles.stateSymbol} aria-hidden="true">
          {symbol}
        </span>
        <h2 className={styles.stateTitle}>{title}</h2>
        <p className={styles.stateText}>{text}</p>
      </div>
    </div>
  );
}
