import { useQuery } from "@tanstack/react-query";

import { getJson } from "../api/client";
import { API_PATHS, type UserCollection } from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

export function AdminPage() {
  const users = useQuery({
    queryKey: ["admin", "users"],
    queryFn: ({ signal }) => getJson<UserCollection>(API_PATHS.adminUsers, signal),
    staleTime: 30_000,
  });

  return (
    <section className={styles.page} aria-labelledby="admin-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Platform authorization / role mapping</p>
          <h1 className={styles.title} id="admin-title">
            Admin
          </h1>
          <p className={styles.lede}>
            Identity Provider 只证明身份；Knowledge Ledger 自己维护产品角色、权限和禁用状态。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>Credential policy</span>
          <span className={styles.asideValue}>Secrets never echoed</span>
        </div>
      </header>

      <div className={styles.panel}>
        {users.data?.data.partial ? (
          <div className={styles.notice} role="status">
            △ {users.data.data.warnings.join("；") || "用户列表为部分数据。"}
          </div>
        ) : null}
        {users.isPending ? (
          <div className={styles.statePanel} aria-busy="true">
            <div>
              <span className={styles.stateSymbol}>…</span>
              <h2 className={styles.stateTitle}>正在读取授权映射</h2>
            </div>
          </div>
        ) : null}
        {users.isError ? (
          <div className={`${styles.statePanel} ${styles.error}`} role="alert">
            <div>
              <span className={styles.stateSymbol}>!</span>
              <h2 className={styles.stateTitle}>Admin API 不可用</h2>
              <p className={styles.stateText}>权限列表不会从前端缓存或 OIDC claim 推导。</p>
            </div>
          </div>
        ) : null}
        {users.isSuccess && users.data.data.items.length === 0 ? (
          <div className={styles.statePanel} role="status">
            <div>
              <span className={styles.stateSymbol}>∅</span>
              <h2 className={styles.stateTitle}>没有已映射用户</h2>
              <p className={styles.stateText}>OIDC 身份出现后仍需显式分配产品角色。</p>
            </div>
          </div>
        ) : null}
        {users.isSuccess && users.data.data.items.length > 0 ? (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Identity source</th>
                  <th>Product roles</th>
                  <th>Status</th>
                  <th>Last active</th>
                </tr>
              </thead>
              <tbody>
                {users.data.data.items.map((user) => (
                  <tr key={user.userId}>
                    <td>
                      <span className={styles.primary}>{user.displayName}</span>
                      <span className={styles.secondary}>
                        {user.email} · {user.userId}
                      </span>
                    </td>
                    <td className={styles.mono}>{user.identitySource}</td>
                    <td>{user.roles.join(", ")}</td>
                    <td>
                      <span
                        className={`${styles.status} ${
                          user.status === "active" ? styles.statusActive : styles.statusDisabled
                        }`}
                      >
                        {user.status}
                      </span>
                    </td>
                    <td className={styles.mono}>{user.lastActiveAt ?? "never"}</td>
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
