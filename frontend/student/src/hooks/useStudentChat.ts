import { useState } from "react";
import { fetchStudentChat } from "@emoedu/shared";
import type { ChatRequest, RiskLevel, StudentChatView } from "@emoedu/shared";

const FALLBACK_TEXT = "我现在有点没反应过来，要不你再说一次？";

export function useStudentChat(sessionId: string) {
  const [loading, setLoading] = useState(false);
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("green");
  const [referralLocked, setReferralLocked] = useState(false);

  async function send(text: string): Promise<StudentChatView> {
    setLoading(true);

    try {
      const request: ChatRequest = {
        session_id: sessionId,
        current_message: text,
      };
      const view = await fetchStudentChat(request);

      setRiskLevel(view.risk_level);
      setReferralLocked(view.risk_level !== "green");

      return view;
    } catch {
      const fallback: StudentChatView = {
        session_id: sessionId,
        reply_text: FALLBACK_TEXT,
        risk_level: "green",
      };

      setRiskLevel(fallback.risk_level);
      setReferralLocked(false);

      return fallback;
    } finally {
      setLoading(false);
    }
  }

  function resetReferral(): void {
    setRiskLevel("green");
    setReferralLocked(false);
  }

  return {
    loading,
    riskLevel,
    referralLocked,
    send,
    resetReferral,
  };
}
