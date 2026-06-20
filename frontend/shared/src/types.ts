export interface ChatRequest {
  session_id: string;
  current_message: string;
  anonymous_user_id?: string;
}

export type ChatStatus =
  | "answered"
  | "blocked_by_safety"
  | "all_candidates_blocked"
  | "module_failed";

export type RiskLevel = "green" | "yellow" | "red";

export type ScenarioLabel = "学业压力" | "同伴关系" | "亲子摩擦" | "其他";

export type GeneratorOrientation = "共情型" | "引导反思型";

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
  anonymous_user_id?: string | null;
  status: ChatStatus;
  reply_text: string;
  risk_level: RiskLevel;
  scenario: ScenarioLabel | null;
  support_mode?: "emotion_first" | "solution_seeking" | "balanced" | null;
  emotion_intensity?: "low" | "medium" | "high" | null;
  help_seeking?: boolean | null;
  selected_by?: string | null;
  activated_casel: string[];
  best_candidate_id: string | null;
  candidates: GeneratorCandidate[];
  scores: CandidateScore[];
  preference_pair: PreferencePair | null;
  failed_module: string | null;
  failure_reason: string;
}

export interface CriticGuidanceStatusResponse {
  session_id: string;
  status: "missing" | "pending" | "ready" | "failed";
  guidance: string;
  scores: CandidateScore[];
  error: string;
  updated_at?: string | null;
}

export interface StudentChatView {
  session_id: string;
  anonymous_user_id?: string | null;
  reply_text: string;
  risk_level: RiskLevel;
}

export type ChatStreamEvent =
  | { event: "stage"; data: { name: string } }
  | { event: "metadata"; data: Omit<FullChatResponse, "reply_text"> }
  | { event: "delta"; data: { text: string } }
  | { event: "done"; data: FullChatResponse }
  | { event: "error"; data: { message: string; session_id?: string; anonymous_user_id?: string | null } };
