import { useState } from "react";
import { Link, Outlet } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";

import { getJson } from "../api/client";
import {
  API_PATHS,
  type CurrentRelease,
  type PlatformHealth,
  type Session,
} from "../contracts/knowledgeApi";
import styles from "./AppShell.module.css";

const navigation = [
  { index: "01", label: "Sources", to: "/sources", badge: "05" },
  { index: "02", label: "Processing", to: "/processing", badge: "03" },
  { index: "03", label: "Candidates", to: "/candidates", badge: "12" },
  { index: "04", label: "Relations", to: "/relations", badge: null },
  { index: "05", label: "Query Lab", to: "/query-lab", badge: null },
  { index: "06", label: "Evaluation", to: "/evaluation", badge: "02" },
  { index: "07", label: "Releases", to: "/releases", badge: "01" },
  { index: "08", label: "Audit", to: "/audit", badge: null },
  { index: "09", label: "Admin", to: "/admin", badge: null },
] as const;

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const session = useQuery({
    queryKey: ["session"],
    queryFn: ({ signal }) => getJson<Session>(API_PATHS.session, signal),
    staleTime: 60_000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => getJson<PlatformHealth>(API_PATHS.health, signal),
    refetchInterval: 30_000,
  });
  const release = useQuery({
    queryKey: ["release", "current"],
    queryFn: ({ signal }) => getJson<CurrentRelease>(API_PATHS.currentRelease, signal),
    staleTime: 30_000,
  });

  const healthState = health.data?.data.status;
  const healthLabel = health.isPending
    ? "checking"
    : health.isError
      ? "unavailable"
      : healthState ?? "unknown";
  const releaseLabel = release.isPending
    ? "loading"
    : release.isError
      ? "unavailable"
      : release.data?.data.version ?? "not released";
  const indexLabel = release.data?.data.indexVersion ?? "not built";
  const sessionData = session.data?.data;

  const closeDrawer = () => setDrawerOpen(false);

  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#main-content">
        跳到主内容
      </a>

      <button
        type="button"
        className={`${styles.overlay} ${drawerOpen ? styles.overlayVisible : ""}`}
        aria-label="关闭导航"
        onClick={closeDrawer}
      />

      <aside
        className={`${styles.sidebar} ${drawerOpen ? styles.sidebarOpen : ""}`}
        aria-label="知识平台主导航"
      >
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">
            K
          </span>
          <span>
            <span className={styles.brandTitle}>Knowledge Ledger</span>
            <span className={styles.brandMeta}>Evidence · Review · Release</span>
          </span>
        </div>

        <nav className={styles.nav}>
          <p className={styles.navGroup}>Knowledge operations</p>
          {navigation.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={styles.navLink}
              activeProps={{ className: `${styles.navLink} ${styles.navLinkActive}` }}
              onClick={closeDrawer}
            >
              <span className={styles.navIndex}>{item.index}</span>
              <span className={styles.navLabel}>{item.label}</span>
              {item.badge ? <span className={styles.navBadge}>{item.badge}</span> : null}
            </Link>
          ))}
        </nav>

        <div className={styles.sidebarFoot}>
          <div>CONTRACT · prerelease.v1</div>
          <div>MODE · API evidence only</div>
        </div>
      </aside>

      <div className={styles.main}>
        <header className={styles.topbar}>
          <button
            type="button"
            className={styles.mobileButton}
            aria-label="打开导航"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            ≡
          </button>

          <div className={styles.facts} aria-label="平台事实">
            <div className={styles.fact}>
              <span className={styles.factLabel}>Platform</span>
              <span className={styles.factValue}>
                <span className={styles.statusLine}>
                  <span
                    className={`${styles.statusDot} ${
                      healthState === "degraded" || health.isError
                        ? styles.statusDotDegraded
                        : ""
                    }`}
                  />
                  {healthLabel}
                </span>
              </span>
            </div>
            <span className={styles.factDivider} aria-hidden="true" />
            <div className={styles.fact}>
              <span className={styles.factLabel}>Current release</span>
              <span className={styles.factValue}>{releaseLabel}</span>
            </div>
            <span className={styles.factDivider} aria-hidden="true" />
            <div className={styles.fact}>
              <span className={styles.factLabel}>Index manifest</span>
              <span className={styles.factValue}>{indexLabel}</span>
            </div>
          </div>

          <div className={styles.identity} aria-label="当前身份">
            <span className={styles.avatar} aria-hidden="true">
              {sessionData ? initials(sessionData.displayName) : "—"}
            </span>
            <span>
              <span className={styles.identityName}>
                {session.isPending
                  ? "Loading identity"
                  : session.isError
                    ? "Identity unavailable"
                    : sessionData?.displayName}
              </span>
              <span className={styles.identityRole}>{sessionData?.role ?? "unknown role"}</span>
            </span>
          </div>
        </header>

        <main id="main-content" className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
