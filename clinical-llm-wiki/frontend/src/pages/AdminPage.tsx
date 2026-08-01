import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, getJson, postJson } from "../api/client";
import {
  API_PATHS,
  roleLabel,
  type ApiResponse,
  type ModelDeploymentClass,
  type ModelProfileCollection,
  type ModelProfileRegistration,
  type ModelProfileRegistrationRequest,
  type UserCollection,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

const REFERENCE_PATTERN = /^(env|secret):\/\/[A-Za-z0-9_./-]+$/;

const initialProfile: ModelProfileRegistrationRequest = {
  profileId: "",
  version: "1.0.0",
  provider: "",
  model: "",
  deploymentClass: "external_api",
  secretRef: "env://KNOWLEDGE_MODEL_API_KEY",
  endpointRef: "env://KNOWLEDGE_MODEL_ENDPOINT",
  allowedDataBoundaries: ["external_allowed"],
  capabilities: ["structured_generation"],
  timeoutSeconds: 60,
  maxOutputTokens: 4096,
  costPolicy: null,
};

export function AdminPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState(initialProfile);
  const [formError, setFormError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);

  const profiles = useQuery({
    queryKey: ["admin", "model-profiles"],
    queryFn: ({ signal }) =>
      getJson<ModelProfileCollection>(API_PATHS.adminModelProfiles, signal),
    staleTime: 30_000,
  });
  const users = useQuery({
    queryKey: ["admin", "users"],
    queryFn: ({ signal }) => getJson<UserCollection>(API_PATHS.adminUsers, signal),
    staleTime: 30_000,
  });

  const registration = useMutation({
    mutationFn: (body: ModelProfileRegistrationRequest) =>
      postJson<ModelProfileRegistration, ModelProfileRegistrationRequest>(
        API_PATHS.adminModelProfiles,
        body,
      ),
    onSuccess: (response) => {
      queryClient.setQueryData<ApiResponse<ModelProfileCollection>>(
        ["admin", "model-profiles"],
        (previous) => {
          const items = previous?.data.items ?? [];
          const profile = response.data.profile;
          const exists = items.some(
            (item) => item.profileId === profile.profileId && item.version === profile.version,
          );
          return {
            data: {
              items: exists ? items : [profile, ...items],
              total: exists ? items.length : items.length + 1,
              partial: previous?.data.partial ?? false,
              warnings: previous?.data.warnings ?? [],
            },
            meta: response.meta,
          };
        },
      );
      setReceipt("配置版本已登记，尚未验证连接或启用 live。");
      setShowForm(false);
    },
    onError: (error) => {
      setFormError(error instanceof Error ? error.message : "配置版本登记失败。");
    },
  });

  function setField<K extends keyof ModelProfileRegistrationRequest>(
    key: K,
    value: ModelProfileRegistrationRequest[K],
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setReceipt(null);
    if (!REFERENCE_PATTERN.test(draft.secretRef)) {
      setFormError("Secret reference 只接受 env:// 或 secret:// 引用。");
      return;
    }
    if (draft.endpointRef && !REFERENCE_PATTERN.test(draft.endpointRef)) {
      setFormError("Endpoint reference 只接受 env:// 或 secret:// 引用。");
      return;
    }
    registration.mutate(draft);
  }

  return (
    <section className={styles.page} aria-labelledby="admin-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Platform configuration / authorization</p>
          <h1 className={styles.title} id="admin-title">Admin</h1>
          <p className={styles.lede}>
            管理模型配置引用和产品角色。凭据值不进入浏览器、响应或审计记录。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>Credential policy</span>
          <span className={styles.asideValue}>Secrets never echoed</span>
        </div>
      </header>

      <div className={styles.adminSection}>
        <div className={styles.sectionHeading}>
          <div>
            <p className={styles.eyebrow}>Configuration registry</p>
            <h2>Model API Configuration</h2>
          </div>
          <div className={styles.buttonRow}>
            <button className={styles.secondaryButton} type="button" onClick={() => void profiles.refetch()}>
              重新读取模型配置
            </button>
            <button
              className={styles.primaryButton}
              type="button"
              onClick={() => setShowForm((current) => !current)}
            >
              登记 ModelProfile 版本
            </button>
          </div>
        </div>
        <div className={styles.gateNote}>
          <strong>配置保存不等于 live 授权。</strong> 本页面不会测试连接、启动 Worker、发送 Evidence 或消耗 API 额度。
        </div>

        {showForm ? (
          <form className={styles.modelForm} onSubmit={submitProfile}>
            <label>Profile ID<input required value={draft.profileId} onChange={(event) => setField("profileId", event.target.value)} /></label>
            <label>Version<input required value={draft.version} onChange={(event) => setField("version", event.target.value)} /></label>
            <label>Provider<input required value={draft.provider} onChange={(event) => setField("provider", event.target.value)} /></label>
            <label>Model<input required value={draft.model} onChange={(event) => setField("model", event.target.value)} /></label>
            <label>
              Deployment class
              <select
                value={draft.deploymentClass}
                onChange={(event) => {
                  const value = event.target.value as ModelDeploymentClass;
                  setDraft((current) => ({
                    ...current,
                    deploymentClass: value,
                    allowedDataBoundaries: [
                      value === "enterprise_managed"
                        ? "enterprise_provider_only"
                        : "external_allowed",
                    ],
                  }));
                }}
              >
                <option value="external_api">External API</option>
                <option value="enterprise_managed">Enterprise managed</option>
              </select>
            </label>
            <label>Data boundary<input readOnly value={draft.allowedDataBoundaries[0]} /></label>
            <label>Secret reference<input required value={draft.secretRef} onChange={(event) => setField("secretRef", event.target.value)} /></label>
            <label>Endpoint reference<input value={draft.endpointRef ?? ""} onChange={(event) => setField("endpointRef", event.target.value || null)} /></label>
            <label>Timeout seconds<input min="1" max="600" type="number" value={draft.timeoutSeconds} onChange={(event) => setField("timeoutSeconds", Number(event.target.value))} /></label>
            <label>Max output tokens<input min="1" type="number" value={draft.maxOutputTokens} onChange={(event) => setField("maxOutputTokens", Number(event.target.value))} /></label>
            <div className={styles.formActions}>
              <button className={styles.primaryButton} disabled={registration.isPending} type="submit">
                {registration.isPending ? "正在登记…" : "保存配置版本"}
              </button>
              <button className={styles.secondaryButton} type="button" onClick={() => setShowForm(false)}>取消</button>
            </div>
          </form>
        ) : null}
        {formError ? <p className={styles.formError} role="alert">{formError}</p> : null}
        {receipt ? <p className={styles.receipt} role="status">{receipt}</p> : null}

        <div className={styles.panel}>
          {profiles.data?.data.partial ? <div className={styles.notice} role="status">△ {profiles.data.data.warnings.join("；") || "模型配置列表为部分数据。"}</div> : null}
          {profiles.isPending ? (
            <div className={styles.compactState} aria-label="正在读取模型配置" aria-busy="true"><strong>正在读取模型配置</strong><span>只读取引用与版本元数据。</span></div>
          ) : null}
          {profiles.isError ? (
            <div className={`${styles.compactState} ${styles.error}`} role="alert">
              <strong>{profiles.error instanceof ApiRequestError ? profiles.error.message : "模型配置 registry 不可用"}</strong>
              <span>使用上方按钮重试；失败不会回退到前端缓存。</span>
            </div>
          ) : null}
          {profiles.isSuccess && profiles.data.data.items.length === 0 ? (
            <div className={styles.compactState} role="status"><strong>尚未登记 ModelProfile</strong><span>登记一个不可变版本，不会触发外部连接。</span></div>
          ) : null}
          {profiles.isSuccess && profiles.data.data.items.length > 0 ? (
            <div className={styles.modelGrid}>
              {profiles.data.data.items.map((profile) => (
                <article className={styles.modelCard} key={`${profile.profileId}@${profile.version}`}>
                  <header><div><span className={styles.eyebrow}>{profile.provider}</span><h3>{profile.model}</h3></div><code>{profile.profileId}@{profile.version}</code></header>
                  <dl>
                    <div><dt>Secret reference</dt><dd>{profile.secretRef}</dd></div>
                    <div><dt>Endpoint reference</dt><dd>{profile.endpointRef ?? "provider default"}</dd></div>
                    <div><dt>Boundary</dt><dd>{profile.allowedDataBoundaries.join(", ")}</dd></div>
                    <div><dt>Limits</dt><dd>{profile.timeoutSeconds}s · {profile.maxOutputTokens} tokens</dd></div>
                  </dl>
                  <footer><span className={styles.status}>not verified</span><span className={`${styles.status} ${styles.statusDisabled}`}>live disabled</span></footer>
                </article>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className={styles.adminSection}>
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>Product authorization</p><h2>Identity &amp; access</h2></div></div>
        <div className={styles.panel}>
          {users.data?.data.partial ? <div className={styles.notice} role="status">△ {users.data.data.warnings.join("；") || "用户列表为部分数据。"}</div> : null}
          {users.isPending ? <div className={styles.statePanel} aria-busy="true"><div><span className={styles.stateSymbol}>…</span><h2 className={styles.stateTitle}>正在读取授权映射</h2></div></div> : null}
          {users.isError ? <div className={`${styles.statePanel} ${styles.error}`} role="alert"><div><span className={styles.stateSymbol}>!</span><h2 className={styles.stateTitle}>Admin API 不可用</h2><p className={styles.stateText}>权限列表不会从前端缓存或 OIDC claim 推导。</p></div></div> : null}
          {users.isSuccess && users.data.data.items.length === 0 ? <div className={styles.statePanel} role="status"><div><span className={styles.stateSymbol}>∅</span><h2 className={styles.stateTitle}>没有已映射用户</h2><p className={styles.stateText}>OIDC 身份出现后仍需显式分配产品角色。</p></div></div> : null}
          {users.isSuccess && users.data.data.items.length > 0 ? (
            <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>User</th><th>Identity source</th><th>Product roles</th><th>Status</th><th>Last active</th></tr></thead><tbody>
              {users.data.data.items.map((user) => <tr key={user.userId}><td><span className={styles.primary}>{user.displayName}</span><span className={styles.secondary}>{user.email} · {user.userId}</span></td><td className={styles.mono}>{user.identitySource}</td><td>{user.roles.map(roleLabel).join(", ")}</td><td><span className={`${styles.status} ${user.status === "active" ? styles.statusActive : styles.statusDisabled}`}>{user.status}</span></td><td className={styles.mono}>{user.lastActiveAt ?? "never"}</td></tr>)}
            </tbody></table></div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
