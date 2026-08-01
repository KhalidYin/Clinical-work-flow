import type { HumanRole } from "../contracts/knowledgeApi";

const STATUS_LABELS: Record<string, string> = {
  active: "已启用",
  disabled: "已禁用",
  registered: "已登记",
  processing: "处理中",
  queued: "已排队",
  succeeded: "已完成",
  failed: "失败",
  expired: "已过期",
  cancelled: "已取消",
  evidence_ready: "证据已就绪",
  author_confirmation_required: "等待作者确认",
  author_confirmed: "作者已确认",
  review_required: "等待独立审核",
  approved: "已批准",
  rejected: "已拒绝",
  changes_requested: "要求修改",
  release_blocked: "发布受阻",
  released: "已发布",
  restricted: "受限",
  superseded: "已取代",
  retired: "已退役",
  proposed: "已提议",
  accepted: "已接受",
  unversioned: "未版本化",
  not_released: "未发布",
  not_verified: "未验证",
};

const ROLE_LABELS: Record<HumanRole, string> = {
  platform_admin: "平台管理员",
  knowledge_curator: "知识工程师",
  reviewer: "知识审核员",
  release_manager: "发布管理员",
  consumer: "知识使用者",
};

export function statusLabel(value: string | null | undefined): string {
  if (!value) return "未记录";
  return STATUS_LABELS[value] ?? value;
}

export function humanRoleLabel(value: HumanRole): string {
  return ROLE_LABELS[value];
}

export function identitySourceLabel(value: string): string {
  return {
    local_password: "本地用户名密码",
    local_test: "旧本地测试身份",
    oidc: "企业 OIDC",
  }[value] ?? value;
}

export function workerPoolLabel(value: string): string {
  return {
    document: "文档处理",
    enrichment: "知识富化",
    release: "版本发布",
  }[value] ?? value;
}

export function rightsLabel(value: string): string {
  return {
    licensed: "已授权",
    internal: "内部资料",
    restricted: "受限资料",
  }[value] ?? value;
}

export function boundaryLabel(value: string): string {
  return {
    local_processing_only: "仅本地处理",
    enterprise_provider_only: "仅企业托管模型",
    external_allowed: "允许外部模型",
    prohibited: "禁止处理",
  }[value] ?? value;
}

export function relationTypeLabel(value: string): string {
  return {
    applies_to: "适用于",
    conflicts_with: "与其冲突",
    depends_on: "依赖于",
    derived_from: "派生自",
    supersedes: "取代",
    supports: "支持",
    used_by: "被使用于",
  }[value] ?? value;
}
