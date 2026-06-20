import { useRef, useState } from "react";
import { fetchStudentChatStream } from "@emoedu/shared";
import type { ChatRequest, RiskLevel, StudentChatView } from "@emoedu/shared";

const FALLBACK_TEXT = "我现在有点没反应过来，要不你再说一次？";
const DEFAULT_RISK_LEVEL: RiskLevel = "green";

type RiskLevelsBySession = Record<string, RiskLevel>;

interface SendOptions {
  isCurrent?: () => boolean;
  onDelta?: (text: string) => void;
}

export function useStudentChat(sessionId: string, anonymousUserId: string) {
  const [pendingSessionIds, setPendingSessionIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [riskLevelsBySession, setRiskLevelsBySession] =
    useState<RiskLevelsBySession>(() => ({}));
  // Conservative fallback: transport/parser failures must not silently downgrade risk.
  const lastKnownRisk = useRef<RiskLevelsBySession>({});
  const loading = pendingSessionIds.has(sessionId);
  const riskLevel = riskLevelsBySession[sessionId] ?? DEFAULT_RISK_LEVEL;
  const isSafetyLocked = riskLevel === "red";

  function setSessionRisk(targetSessionId: string, nextRiskLevel: RiskLevel): void {
    lastKnownRisk.current[targetSessionId] = nextRiskLevel;
    setRiskLevelsBySession((current) => {
      if (current[targetSessionId] === nextRiskLevel) {
        return current;
      }

      return {
        ...current,
        [targetSessionId]: nextRiskLevel,
      };
    });
  }

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
        anonymous_user_id: anonymousUserId,
        current_message: text,
      };
      const view = await fetchStudentChatStream(request, {
        onDelta: (delta: string) => {
          if (options.isCurrent?.() ?? true) {
            options.onDelta?.(delta);
          }
        },
      });

      if (options.isCurrent?.() ?? true) {
        setSessionRisk(requestSessionId, view.risk_level);
      }

      return view;
    } catch {
      const fallback: StudentChatView = {
        session_id: requestSessionId,
        reply_text: FALLBACK_TEXT,
        risk_level: lastKnownRisk.current[requestSessionId] ?? DEFAULT_RISK_LEVEL,
      };

      if (options.isCurrent?.() ?? true) {
        setSessionRisk(requestSessionId, fallback.risk_level);
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

  function resetReferral(targetSessionId = sessionId): void {
    setSessionRisk(targetSessionId, DEFAULT_RISK_LEVEL);
  }

  return {
    loading,
    riskLevel,
    isSafetyLocked,
    send,
    resetReferral,
  };
}
