// ============================================================
// EmoEdu 共享类型定义
// 规格参考: docs/frontend/frontend-cc-spec.md §3
// 与 app/schemas/chat.py ChatResponse 逐字段对齐
// ============================================================

export type ChatStatus =
  | 'answered'
  | 'blocked_by_safety'
  | 'all_candidates_blocked'
  | 'module_failed'

export type RiskLevel = 'green' | 'yellow' | 'red'

export type ScenarioLabel = '学业压力' | '同伴关系' | '亲子摩擦' | '其他'

export type GeneratorOrientation = '共情型' | '引导反思型'

export interface ChatRequest {
  session_id: string
  current_message: string
}

export interface GeneratorCandidate {
  candidate_id: string
  orientation: GeneratorOrientation
  text: string
}

export interface EpitomeScore {
  ER: number // 0-2
  IP: number // 0-2
  EX: number // 0-2
}

export interface CandidateScore {
  candidate_id: string
  epitome: EpitomeScore
  casel: Record<string, number>
  boundary_flag: boolean
  boundary_reason: string
  weighted_total: number
  rationale: string
}

export interface PreferencePair {
  winner_id: string
  loser_id: string
}

// ----------------------------------------------------------------
// 完整响应 — 仅供研究分析台使用
// ----------------------------------------------------------------
export interface FullChatResponse {
  session_id: string
  status: ChatStatus
  reply_text: string
  risk_level: RiskLevel
  scenario: ScenarioLabel | null
  activated_casel: string[]
  best_candidate_id: string | null
  candidates: GeneratorCandidate[]
  scores: CandidateScore[]
  preference_pair: PreferencePair | null
  failed_module: string | null
  failure_reason: string
}

// ----------------------------------------------------------------
// 学生端窄类型 — 铁律：仅含三字段
// 规格 §2：「类型定义只允许包含三个字段」
// ----------------------------------------------------------------
export type StudentChatView = Pick<
  FullChatResponse,
  'session_id' | 'reply_text' | 'risk_level'
>
