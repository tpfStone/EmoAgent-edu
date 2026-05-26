import { useState } from "react";
import { fetchStudentChat } from "@emoedu/shared";
import type { ChatRequest, RiskLevel, StudentChatView } from "@emoedu/shared";

const FALLBACK_TEXT = "我现在有点没反应过来，要不你再说一次？";

interface SendOptions {
  isCurrent?: () => boolean;
}

export function useStudentChat(sessionId: string) {
  const [pendingSessionIds, setPendingSessionIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("green");
  const [referralLocked, setReferralLocked] = useState(false);
  const loading = pendingSessionIds.has(sessionId);

  async function send(
    text: string,
    options: SendOptions = {},
  ): Promise<StudentChatView> {
    const requestSessionId = sessionId;
    setPendingSessionIds((current) => {
      const next = new Set(current);
      next.add(requestSessionId);
      return next;
    });

    try {
      const request: ChatRequest = {
        session_id: requestSessionId,
        current_message: text,
      };
      const view = await fetchStudentChat(request);

      if (options.isCurrent?.() ?? true) {
        setRiskLevel(view.risk_level);
        setReferralLocked(view.risk_level !== "green");
      }

      return view;
    } catch {
      const fallback: StudentChatView = {
        session_id: requestSessionId,
        reply_text: FALLBACK_TEXT,
        risk_level: "green",
      };

      if (options.isCurrent?.() ?? true) {
        setRiskLevel(fallback.risk_level);
        setReferralLocked(false);
      }

      return fallback;
    } finally {
      setPendingSessionIds((current) => {
        const next = new Set(current);
        next.delete(requestSessionId);
        return next;
      });
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
