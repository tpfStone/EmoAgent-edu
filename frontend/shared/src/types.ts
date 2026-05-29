export interface ChatRequest {
  session_id: string;
  current_message: string;
}

export type ChatStatus =
  | "answered"
  | "blocked_by_safety"
  | "all_candidates_blocked"
  | "module_failed";

export type RiskLevel = "green" | "yellow" | "red";

export type ScenarioLabel = "学业压力" | "同伴关系" | "亲子摩擦" | "其他";

export type GeneratorOrientation = "情感共情型" | "认知共情型";

export interface GeneratorCandidate {
  candidate_id: string;
  orientation: GeneratorOrientation;
  text: string;
}

export interface EpitomeScore {
  ER: number;
  IP: number;
  EX: number;
}

export interface CandidateScore {
  candidate_id: string;
  epitome: EpitomeScore;
  casel: Record<string, number>;
  boundary_flag: boolean;
  boundary_reason: string;
  weighted_total: number;
  rationale: string;
}

export interface PreferencePair {
  winner_id: string;
  loser_id: string;
}

export interface FullChatResponse {
  session_id: string;
  status: ChatStatus;
  reply_text: string;
  risk_level: RiskLevel;
  scenario: ScenarioLabel | null;
  activated_casel: string[];
  best_candidate_id: string | null;
  candidates: GeneratorCandidate[];
  scores: CandidateScore[];
  preference_pair: PreferencePair | null;
  failed_module: string | null;
  failure_reason: string;
}

export interface StudentChatView {
  session_id: string;
  reply_text: string;
  risk_level: RiskLevel;
}
