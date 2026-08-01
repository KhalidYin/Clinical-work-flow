import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, getJson, postAction, postJson } from "../api/client";
import {
  API_PATHS,
  adminUserPasswordResetPath,
  adminUserStatusPath,
  roleLabel,
  type AdminTemporaryPassword,
  type ApiResponse,
  type HumanRole,
  type ModelDeploymentClass,
  type ModelProfileCollection,
  type ModelProfileRegistration,
  type ModelProfileRegistrationRequest,
  type ServiceAccountCollection,
  type UserCollection,
  type UserCreateRequest,
  type UserStatusReceipt,
  type UserStatusRequest,
} from "../contracts/knowledgeApi";
import { identitySourceLabel, statusLabel, workerPoolLabel } from "../i18n/labels";
import styles from "./pages.module.css";

const REFERENCE_PATTERN = /^(env|secret):\/\/[A-Za-z0-9_./-]+$/;
const HUMAN_ROLES: HumanRole[] = [
  "platform_admin",
  "knowledge_curator",
  "reviewer",
  "release_manager",
  "consumer",
];

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

const initialUser: UserCreateRequest = {
  username: "",
  displayName: "",
  email: "",
  roles: ["consumer"],
};

export function AdminPage() {
  const queryClient = useQueryClient();
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [profileDraft, setProfileDraft] = useState(initialProfile);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileReceipt, setProfileReceipt] = useState<string | null>(null);
  const [showUserForm, setShowUserForm] = useState(false);
  const [userDraft, setUserDraft] = useState(initialUser);
  const [userError, setUserError] = useState<string | null>(null);
  const [temporaryCredential, setTemporaryCredential] =
    useState<AdminTemporaryPassword | null>(null);

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
  const serviceAccounts = useQuery({
    queryKey: ["admin", "service-accounts"],
    queryFn: ({ signal }) =>
      getJson<ServiceAccountCollection>(API_PATHS.adminServiceAccounts, signal),
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
      setProfileReceipt("配置版本已登记，尚未验证连接或启用实时调用。");
      setShowProfileForm(false);
    },
    onError: (error) => setProfileError(errorMessage(error, "配置版本登记失败。")),
  });

  const createUser = useMutation({
    mutationFn: (body: UserCreateRequest) =>
      postJson<AdminTemporaryPassword, UserCreateRequest>(API_PATHS.adminUsers, body),
    onSuccess: async (response) => {
      setTemporaryCredential(response.data);
      setShowUserForm(false);
      setUserDraft(initialUser);
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (error) => setUserError(errorMessage(error, "创建用户失败。")),
  });
  const resetPassword = useMutation({
    mutationFn: (userId: string) =>
      postAction<AdminTemporaryPassword>(adminUserPasswordResetPath(userId)),
    onSuccess: (response) => setTemporaryCredential(response.data),
    onError: (error) => setUserError(errorMessage(error, "重置密码失败。")),
  });
  const changeStatus = useMutation({
    mutationFn: ({ userId, status }: { userId: string; status: "active" | "disabled" }) =>
      postJson<UserStatusReceipt, UserStatusRequest>(adminUserStatusPath(userId), { status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (error) => setUserError(errorMessage(error, "变更用户状态失败。")),
  });

  function setProfileField<K extends keyof ModelProfileRegistrationRequest>(
    key: K,
    value: ModelProfileRegistrationRequest[K],
  ) {
    setProfileDraft((current) => ({ ...current, [key]: value }));
  }

  function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileError(null);
    setProfileReceipt(null);
    if (!REFERENCE_PATTERN.test(profileDraft.secretRef)) {
      setProfileError("密钥引用只接受 env:// 或 secret:// 引用。");
      return;
    }
    if (profileDraft.endpointRef && !REFERENCE_PATTERN.test(profileDraft.endpointRef)) {
      setProfileError("端点引用只接受 env:// 或 secret:// 引用。");
      return;
    }
    registration.mutate(profileDraft);
  }

  function submitUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUserError(null);
    setTemporaryCredential(null);
    if (userDraft.roles.length === 0) {
      setUserError("至少选择一个产品角色。");
      return;
    }
    createUser.mutate(userDraft);
  }

  const userActionPending = resetPassword.isPending || changeStatus.isPending;

  return (
    <section className={styles.page} aria-labelledby="admin-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>平台配置 / 权限治理</p>
          <h1 className={styles.title} id="admin-title">系统管理</h1>
          <p className={styles.lede}>管理人员账号、只读查看工作进程机器身份，并登记不含密钥值的模型配置引用。</p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>凭据策略</span>
          <span className={styles.asideValue}>人员密码与机器凭据严格分离</span>
        </div>
      </header>

      <div className={styles.adminSection}>
        <div className={styles.sectionHeading}>
          <div><p className={styles.eyebrow}>人员账号与产品权限</p><h2>用户管理</h2></div>
          <div className={styles.buttonRow}>
            <button className={styles.secondaryButton} type="button" onClick={() => void users.refetch()}>重新读取用户</button>
            <button className={styles.primaryButton} type="button" onClick={() => { setShowUserForm((value) => !value); setUserError(null); }}>创建用户</button>
          </div>
        </div>
        <div className={styles.gateNote}><strong>人员用户只使用用户名和密码。</strong> 创建与重置只返回一次临时密码；用户首次登录必须修改。</div>

        {showUserForm ? (
          <form className={styles.modelForm} onSubmit={submitUser}>
            <label>用户名<input required autoComplete="off" value={userDraft.username} onChange={(event) => setUserDraft((value) => ({ ...value, username: event.target.value }))} /></label>
            <label>显示名称<input required value={userDraft.displayName} onChange={(event) => setUserDraft((value) => ({ ...value, displayName: event.target.value }))} /></label>
            <label>邮箱<input required type="email" value={userDraft.email} onChange={(event) => setUserDraft((value) => ({ ...value, email: event.target.value }))} /></label>
            <fieldset className={styles.roleFieldset}>
              <legend>产品角色</legend>
              {HUMAN_ROLES.map((role) => (
                <label key={role}>
                  <input type="checkbox" checked={userDraft.roles.includes(role)} onChange={(event) => setUserDraft((value) => ({ ...value, roles: event.target.checked ? [...value.roles, role] : value.roles.filter((item) => item !== role) }))} />
                  {roleLabel(role)} <code>{role}</code>
                </label>
              ))}
            </fieldset>
            <div className={styles.formActions}>
              <button className={styles.primaryButton} disabled={createUser.isPending} type="submit">{createUser.isPending ? "正在创建…" : "创建并生成临时密码"}</button>
              <button className={styles.secondaryButton} type="button" onClick={() => setShowUserForm(false)}>取消</button>
            </div>
          </form>
        ) : null}
        {temporaryCredential ? (
          <div className={styles.temporaryCredential} role="status" aria-label="一次性临时密码">
            <div><span className={styles.eyebrow}>仅显示一次</span><strong>{temporaryCredential.username ?? temporaryCredential.userId}</strong></div>
            <code>{temporaryCredential.temporaryPassword}</code>
            <p>请通过受控渠道交给该用户。关闭后无法再次查看；如遗失，只能重新生成。</p>
            <button className={styles.secondaryButton} type="button" onClick={() => setTemporaryCredential(null)}>我已安全保存</button>
          </div>
        ) : null}
        {userError ? <p className={styles.formError} role="alert">{userError}</p> : null}

        <div className={styles.panel}>
          {users.data?.data.partial ? <div className={styles.notice} role="status">△ {users.data.data.warnings.join("；") || "用户列表为部分数据。"}</div> : null}
          {users.isPending ? <CompactState title="正在读取用户" text="从 PostgreSQL 权限记录读取，不使用前端缓存。" loading /> : null}
          {users.isError ? <CompactState title="用户管理 API 不可用" text="权限列表不会从浏览器或外部声明推导。" error /> : null}
          {users.isSuccess && users.data.data.items.length === 0 ? <CompactState title="尚无人员用户" text="先创建一名本地用户并分配产品角色。" /> : null}
          {users.isSuccess && users.data.data.items.length > 0 ? (
            <div className={styles.tableWrap}><table className={styles.table}>
              <thead><tr><th>用户</th><th>登录来源</th><th>产品角色</th><th>状态</th><th>最近登录</th><th>安全操作</th></tr></thead>
              <tbody>{users.data.data.items.map((user) => (
                <tr key={user.userId}>
                  <td><span className={styles.primary}>{user.displayName}</span><span className={styles.secondary}>{user.email} · {user.userId}</span></td>
                  <td><span>{identitySourceLabel(user.identitySource)}</span><span className={styles.secondary}>{user.identitySource}</span></td>
                  <td>{user.roles.map(roleLabel).join("、")}</td>
                  <td><span className={`${styles.status} ${user.status === "active" ? styles.statusActive : styles.statusDisabled}`}>{statusLabel(user.status)}</span></td>
                  <td className={styles.mono}>{user.lastActiveAt ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short", hour12: false }).format(new Date(user.lastActiveAt)) : "从未登录"}</td>
                  <td><div className={styles.buttonRow}>
                    <button className={styles.secondaryButton} type="button" disabled={userActionPending} onClick={() => resetPassword.mutate(user.userId)}>重置密码</button>
                    <button className={user.status === "active" ? styles.dangerButton : styles.secondaryButton} type="button" disabled={userActionPending} onClick={() => changeStatus.mutate({ userId: user.userId, status: user.status === "active" ? "disabled" : "active" })}>{user.status === "active" ? "禁用" : "启用"}</button>
                  </div></td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : null}
        </div>
      </div>

      <div className={styles.adminSection}>
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>异步工作进程 / 最小权限</p><h2>服务账号</h2></div></div>
        <div className={styles.gateNote}><strong>只读安全投影。</strong> 页面只显示工作池与权限范围，不返回、复制或复用机器凭据引用和值。</div>
        <div className={styles.panel}>
          {serviceAccounts.isPending ? <CompactState title="正在读取服务账号" text="凭据值不进入响应。" loading /> : null}
          {serviceAccounts.isError ? <CompactState title="服务账号 API 不可用" text="不会使用人员账号代替工作进程身份。" error /> : null}
          {serviceAccounts.isSuccess && serviceAccounts.data.data.items.length === 0 ? <CompactState title="尚无服务账号" text="工作进程必须先由后端配置最小权限机器身份。" /> : null}
          {serviceAccounts.isSuccess && serviceAccounts.data.data.items.length > 0 ? (
            <div className={styles.tableWrap}><table className={styles.table}>
              <thead><tr><th>服务账号</th><th>工作池</th><th>最小权限范围</th><th>状态</th></tr></thead>
              <tbody>{serviceAccounts.data.data.items.map((account) => (
                <tr key={account.serviceAccountId}><td><span className={styles.primary}>{account.displayName}</span><span className={styles.secondary}>{account.serviceAccountId}</span></td><td>{workerPoolLabel(account.workerPool)} <code>{account.workerPool}</code></td><td className={styles.mono}>{account.scopes.join(" · ")}</td><td><span className={styles.status}>{statusLabel(account.status)}</span></td></tr>
              ))}</tbody>
            </table></div>
          ) : null}
        </div>
      </div>

      <div className={styles.adminSection}>
        <div className={styles.sectionHeading}>
          <div><p className={styles.eyebrow}>外部模型配置登记</p><h2>模型 API 配置</h2></div>
          <div className={styles.buttonRow}>
            <button className={styles.secondaryButton} type="button" onClick={() => void profiles.refetch()}>重新读取模型配置</button>
            <button className={styles.primaryButton} type="button" onClick={() => setShowProfileForm((current) => !current)}>登记 ModelProfile 版本</button>
          </div>
        </div>
        <div className={styles.gateNote}><strong>保存配置不等于授权实时调用。</strong> 本页面不会测试连接、启动工作进程、发送证据或消耗 API 额度。</div>

        {showProfileForm ? (
          <form className={styles.modelForm} onSubmit={submitProfile}>
            <label>配置 ID（Profile ID）<input required value={profileDraft.profileId} onChange={(event) => setProfileField("profileId", event.target.value)} /></label>
            <label>版本（Version）<input required value={profileDraft.version} onChange={(event) => setProfileField("version", event.target.value)} /></label>
            <label>提供方（Provider）<input required value={profileDraft.provider} onChange={(event) => setProfileField("provider", event.target.value)} /></label>
            <label>模型（Model）<input required value={profileDraft.model} onChange={(event) => setProfileField("model", event.target.value)} /></label>
            <label>部署类型<select value={profileDraft.deploymentClass} onChange={(event) => { const value = event.target.value as ModelDeploymentClass; setProfileDraft((current) => ({ ...current, deploymentClass: value, allowedDataBoundaries: [value === "enterprise_managed" ? "enterprise_provider_only" : "external_allowed"] })); }}><option value="external_api">外部 API（external_api）</option><option value="enterprise_managed">企业托管（enterprise_managed）</option></select></label>
            <label>数据边界<input readOnly value={profileDraft.allowedDataBoundaries[0]} /></label>
            <label>密钥引用（Secret reference）<input required value={profileDraft.secretRef} onChange={(event) => setProfileField("secretRef", event.target.value)} /></label>
            <label>端点引用（Endpoint reference）<input value={profileDraft.endpointRef ?? ""} onChange={(event) => setProfileField("endpointRef", event.target.value || null)} /></label>
            <label>超时秒数<input min="1" max="600" type="number" value={profileDraft.timeoutSeconds} onChange={(event) => setProfileField("timeoutSeconds", Number(event.target.value))} /></label>
            <label>最大输出 token 数<input min="1" type="number" value={profileDraft.maxOutputTokens} onChange={(event) => setProfileField("maxOutputTokens", Number(event.target.value))} /></label>
            <div className={styles.formActions}><button className={styles.primaryButton} disabled={registration.isPending} type="submit">{registration.isPending ? "正在登记…" : "保存配置版本"}</button><button className={styles.secondaryButton} type="button" onClick={() => setShowProfileForm(false)}>取消</button></div>
          </form>
        ) : null}
        {profileError ? <p className={styles.formError} role="alert">{profileError}</p> : null}
        {profileReceipt ? <p className={styles.receipt} role="status">{profileReceipt}</p> : null}
        <div className={styles.panel}>
          {profiles.data?.data.partial ? <div className={styles.notice} role="status">△ {profiles.data.data.warnings.join("；") || "模型配置列表为部分数据。"}</div> : null}
          {profiles.isPending ? <CompactState title="正在读取模型配置" text="只读取引用与版本元数据。" loading /> : null}
          {profiles.isError ? <CompactState title={profiles.error instanceof ApiRequestError ? profiles.error.message : "模型配置登记表不可用"} text="失败不会回退到前端缓存。" error /> : null}
          {profiles.isSuccess && profiles.data.data.items.length === 0 ? <CompactState title="尚未登记 ModelProfile" text="登记不可变版本不会触发外部连接。" /> : null}
          {profiles.isSuccess && profiles.data.data.items.length > 0 ? (
            <div className={styles.modelGrid}>{profiles.data.data.items.map((profile) => (
              <article className={styles.modelCard} key={`${profile.profileId}@${profile.version}`}>
                <header><div><span className={styles.eyebrow}>{profile.provider}</span><h3>{profile.model}</h3></div><code>{profile.profileId}@{profile.version}</code></header>
                <dl><div><dt>密钥引用</dt><dd>{profile.secretRef}</dd></div><div><dt>端点引用</dt><dd>{profile.endpointRef ?? "使用提供方默认值"}</dd></div><div><dt>数据边界</dt><dd>{profile.allowedDataBoundaries.join(", ")}</dd></div><div><dt>调用限制</dt><dd>{profile.timeoutSeconds} 秒 · {profile.maxOutputTokens} tokens</dd></div></dl>
                <footer><span className={styles.status}>未验证</span><span className={`${styles.status} ${styles.statusDisabled}`}>实时调用已禁用</span></footer>
              </article>
            ))}</div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function CompactState({ title, text, error = false, loading = false }: { title: string; text: string; error?: boolean; loading?: boolean }) {
  return <div className={`${styles.compactState} ${error ? styles.error : ""}`} role={error ? "alert" : "status"} aria-label={title} aria-busy={loading || undefined}><strong>{title}</strong><span>{text}</span></div>;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
