// 中文映射：技术值 -> 中文展示（代码/API 字段保持英文，仅展示层翻译）

export const STATUS_ZH: Record<string, string> = {
  RUNNING: '运行中',
  SUCCESS: '成功',
  FAILED: '失败',
  WAITING_APPROVAL: '待审批',
  PENDING: '待开始',
  NOT_FOUND: '未找到',
  NOT_REQUIRED: '无需审批',
  APPROVED: '已批准',
  REJECTED: '已拒绝',
}

export const SEVERITY_ZH: Record<string, string> = {
  HIGH: '高',
  MEDIUM: '中',
  LOW: '低',
}

export const RISK_ZH: Record<string, string> = {
  HIGH: '高风险',
  MEDIUM: '中风险',
  LOW: '低风险',
}

export const ISSUE_TYPE_ZH: Record<string, string> = {
  format_error: '格式异常',
  missing_value: '缺失值',
  duplicate: '重复数据',
  outlier: '离群值',
  whitespace: '空白字符',
  data_quality: '数据质量问题',
}

export const EVENT_ZH: Record<string, string> = {
  WORKFLOW_START: '工作流启动',
  AGENT_START: 'Agent 开始',
  AGENT_DECISION: 'Agent 决策',
  TOOL_CALL: '工具调用',
  TOOL_RESULT: '工具结果',
  STATE_CHANGE: '状态变更',
  HUMAN_APPROVAL: '人工审批',
  VALIDATION: '验证',
  ERROR: '错误',
  WORKFLOW_END: '工作流结束',
}

export const NODE_ZH: Record<string, string> = {
  supervisor: '总控 Agent',
  profiler: '画像 Agent',
  inspector: '质检 Agent',
  planner: '规划 Agent',
  plan_validator: '计划校验',
  risk: '风险评估',
  approval: '人工审批',
  execution: '执行引擎',
  validator: '结果验证',
  reflection: '反思重规划',
  workflow: '工作流',
}

export const TOOL_ZH: Record<string, string> = {
  normalize_phone: '手机号归一化',
  normalize_email: '邮箱归一化',
  normalize_date: '日期归一化',
  trim_whitespace: '去除首尾空白',
  fill_missing: '缺失值填充',
  delete_duplicate: '删除重复行',
  profile_dataset: '数据画像',
  detect_missing: '缺失检测',
  detect_duplicate: '重复检测',
  detect_pattern: '格式检测',
  detect_outlier: '离群检测',
}

export const SOURCE_ZH: Record<string, string> = {
  file: '文件',
  database: '数据库',
  web: '网页',
}

export function zh(v: string | undefined | null, map: Record<string, string>, fallback = '未知'): string {
  if (!v) return fallback
  return map[v] ?? v
}

// 双语文案：英文原值保留 + 旁边中文注释，例如 `WAITING_APPROVAL（待审批）`
export function enZh(v: string | undefined | null, map: Record<string, string>, fallback = '未知'): string {
  if (!v) return fallback
  const cn = map[v]
  if (!cn || cn === v) return v
  return `${v}（${cn}）`
}
