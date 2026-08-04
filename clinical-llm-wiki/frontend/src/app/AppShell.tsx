import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, Outlet } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiRequestError,
  getJson,
  postJson,
  postNoContent,
} from "../api/client";
import {
  API_PATHS,
  roleLabel,
  type CandidateCollection,
  type CurrentRelease,
  type LoginRequest,
  type PasswordChangeRequest,
  type PlatformHealth,
  type ProcessingRunCollection,
  type Session,
  type SourceCollection,
} from "../contracts/knowledgeApi";
import styles from "./AppShell.module.css";

const navigationBase = [
  { index: "01", label: "来源管理", to: "/sources", countKey: "sources" as const },
  { index: "02", label: "处理任务", to: "/processing", countKey: "processing" as const },
  { index: "03", label: "知识候选", to: "/candidates", countKey: "candidates" as const },
  { index: "04", label: "关系浏览", to: "/relations", countKey: null },
  { index: "05", label: "检索实验室", to: "/query-lab", countKey: null },
  { index: "06", label: "质量评估", to: "/evaluation", countKey: null },
  { index: "07", label: "版本发布", to: "/releases", countKey: null },
  { index: "08", label: "审计记录", to: "/audit", countKey: null },
  { index: "09", label: "系统管理", to: "/admin", countKey: null, adminOnly: true as const },
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
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia("(max-width: 980px)").matches;
  });
  const queryClient = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: ({ signal }) => getJson<Session>(API_PATHS.session, signal),
    staleTime: 60_000,
  });
  const authenticationRequired =
    session.error instanceof ApiRequestError && session.error.status === 401;
  const sessionAuthenticated = !authenticationRequired && !session.isPending;

  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => getJson<PlatformHealth>(API_PATHS.health, signal),
    refetchInterval: 30_000,
    enabled: sessionAuthenticated,
  });
  const release = useQuery({
    queryKey: ["release", "current"],
    queryFn: ({ signal }) => getJson<CurrentRelease>(API_PATHS.currentRelease, signal),
    staleTime: 30_000,
    enabled: sessionAuthenticated,
  });
  const sourcesCount = useQuery({
    queryKey: ["sources"],
    queryFn: ({ signal }) => getJson<SourceCollection>(API_PATHS.sources, signal),
    staleTime: 30_000,
    enabled: sessionAuthenticated,
  });
  const processingCount = useQuery({
    queryKey: ["processing-runs"],
    queryFn: ({ signal }) =>
      getJson<ProcessingRunCollection>(API_PATHS.processingRuns, signal),
    staleTime: 30_000,
    enabled: sessionAuthenticated,
  });
  const candidatesCount = useQuery({
    queryKey: ["candidates"],
    queryFn: ({ signal }) =>
      getJson<CandidateCollection>(API_PATHS.candidates, signal),
    staleTime: 30_000,
    enabled: sessionAuthenticated,
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(max-width: 980px)");
    const onChange = (event: MediaQueryListEvent) => setIsMobile(event.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  const navigation = useMemo(() => {
    const counts: Record<string, string | null> = {};
    const sourceData = sourcesCount.data?.data;
    if (sourceData?.total !== undefined) {
      counts.sources = String(sourceData.total).padStart(2, "0");
    }
    const procData = processingCount.data?.data;
    if (procData?.items !== undefined) {
      const active = procData.items.filter(
        (run) => run.status === "queued" || run.status === "processing",
      ).length;
      counts.processing = active > 0 ? `${active}活跃` : String(procData.total).padStart(2, "0");
    }
    const candData = candidatesCount.data?.data;
    if (candData?.total !== undefined) {
      counts.candidates = String(candData.total).padStart(2, "0");
    }
    return navigationBase
      .filter((item) => {
        if ("adminOnly" in item && item.adminOnly) {
          return session.data?.data?.permissions?.includes("admin:read") ?? false;
        }
        return true;
      })
      .map((item) => ({
        ...item,
        badge: item.countKey ? (counts[item.countKey] ?? null) : null,
      }));
  }, [
    sourcesCount.data?.data,
    processingCount.data?.data,
    candidatesCount.data?.data,
    session.data?.data?.permissions,
  ]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const submitLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!username.trim() || !password) {
      setLoginError("请输入用户名和密码。");
      return;
    }
    setSubmitting(true);
    setLoginError("");
    try {
      const response = await postJson<Session, LoginRequest>(API_PATHS.login, {
        username: username.trim(),
        password,
      });
      queryClient.setQueryData(["session"], response);
      setPassword("");
    } catch (error) {
      setLoginError(
        error instanceof ApiRequestError ? error.message : "登录失败，请稍后重试。",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const submitPasswordChange = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setLoginError("两次输入的新密码不一致。");
      return;
    }
    setSubmitting(true);
    setLoginError("");
    try {
      const response = await postJson<Session, PasswordChangeRequest>(
        API_PATHS.changePassword,
        { currentPassword, newPassword },
      );
      queryClient.setQueryData(["session"], response);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      setLoginError(
        error instanceof ApiRequestError ? error.message : "修改密码失败，请稍后重试。",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const logout = async () => {
    setLoginError("");
    try {
      await postNoContent(API_PATHS.logout);
      queryClient.removeQueries();
      await session.refetch();
    } catch (error) {
      setLoginError(
        error instanceof ApiRequestError
          ? error.message
          : "退出登录失败，请稍后重试。",
      );
    }
  };

  if (authenticationRequired) {
    return (
      <main className={styles.loginShell}>
        <section className={styles.loginPanel} aria-labelledby="login-title">
          <div className={styles.loginMark} aria-hidden="true">
            K
          </div>
          <p className={styles.loginEyebrow}>临床知识台账 · 安全登录</p>
          <h1 id="login-title">登录临床知识台账</h1>
          <p className={styles.loginLead}>
            使用管理员分配的用户名和密码。浏览器仅使用 HttpOnly 会话 Cookie，无法读取或保存人员凭据令牌。
          </p>
          <form className={styles.loginForm} onSubmit={submitLogin}>
            <label htmlFor="username">用户名</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
            <label htmlFor="password">密码</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-describedby={loginError ? "login-error" : undefined}
            />
            {loginError ? (
              <p id="login-error" className={styles.loginError} role="alert">
                {loginError}
              </p>
            ) : null}
            <button type="submit" disabled={submitting}>
              {submitting ? "正在登录…" : "登录"}
            </button>
          </form>
          <p className={styles.loginBoundary}>
            Argon2id 密码哈希 · HttpOnly 会话 · 产品级权限控制
          </p>
        </section>
      </main>
    );
  }

  const sessionData = session.data?.data;
  if (sessionData?.mustChangePassword) {
    return (
      <main className={styles.loginShell}>
        <section className={styles.loginPanel} aria-labelledby="password-change-title">
          <div className={styles.loginMark} aria-hidden="true">K</div>
          <p className={styles.loginEyebrow}>首次登录安全门禁</p>
          <h1 id="password-change-title">请先修改临时密码</h1>
          <p className={styles.loginLead}>新密码长度应为 12–128 个字符，修改成功后会自动轮换会话。</p>
          <form className={styles.loginForm} onSubmit={submitPasswordChange}>
            <label htmlFor="current-password">当前临时密码</label>
            <input id="current-password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
            <label htmlFor="new-password">新密码</label>
            <input id="new-password" type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            <label htmlFor="confirm-password">确认新密码</label>
            <input id="confirm-password" type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
            {loginError ? <p className={styles.loginError} role="alert">{loginError}</p> : null}
            <button type="submit" disabled={submitting}>{submitting ? "正在修改…" : "修改密码并继续"}</button>
          </form>
        </section>
      </main>
    );
  }

  const healthState = health.data?.data.status;
  const healthLabel = health.isPending
    ? "检查中"
    : health.isError
      ? "不可用"
      : healthState === "healthy"
        ? "正常"
        : healthState === "degraded"
          ? "降级"
          : "未知";
  const releaseLabel = release.isPending
    ? "读取中"
    : release.isError
      ? "不可用"
      : release.data?.data.version ?? "尚未发布";
  const indexLabel = release.data?.data.indexVersion ?? "尚未构建";
  const closeDrawer = () => setDrawerOpen(false);

  const sidebarInert = isMobile && !drawerOpen;

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
        inert={sidebarInert || undefined}
        aria-hidden={sidebarInert || undefined}
      >
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">
            K
          </span>
          <span>
            <span className={styles.brandTitle}>临床知识台账</span>
            <span className={styles.brandMeta}>证据 · 审核 · 发布</span>
          </span>
        </div>

        <nav className={styles.nav}>
          <p className={styles.navGroup}>知识治理工作区</p>
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
          <div>契约 · prerelease.v1</div>
          <div>模式 · 仅使用 API 证据</div>
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
              <span className={styles.factLabel}>平台状态</span>
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
              <span className={styles.factLabel}>当前发布</span>
              <span className={styles.factValue}>{releaseLabel}</span>
            </div>
            <span className={styles.factDivider} aria-hidden="true" />
            <div className={styles.fact}>
              <span className={styles.factLabel}>索引清单</span>
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
                  ? "正在加载身份"
                  : session.isError
                    ? "身份不可用"
                    : sessionData?.displayName}
              </span>
              <span className={styles.identityRole}>
                {sessionData?.roles.map(roleLabel).join("、") ?? "角色未知"}
              </span>
            </span>
            {sessionData ? (
              <button
                type="button"
                className={styles.changeIdentity}
                onClick={logout}
              >
                退出登录
              </button>
            ) : null}
          </div>
        </header>

        <main id="main-content" className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
