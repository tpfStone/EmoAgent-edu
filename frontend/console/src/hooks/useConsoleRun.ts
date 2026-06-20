import { useCallback, useState } from "react";
import {
  fetchChat,
  fetchCriticGuidance,
  type ChatRequest,
  type CriticGuidanceStatusResponse,
  type FullChatResponse,
} from "@emoedu/shared/console";

const GUIDANCE_POLL_ATTEMPTS = 120;
const GUIDANCE_POLL_INTERVAL_MS = 1000;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useConsoleRun() {
  const [result, setResult] = useState<FullChatResponse | null>(null);
  const [criticGuidance, setCriticGuidance] =
    useState<CriticGuidanceStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [guidanceLoading, setGuidanceLoading] = useState(false);
  const [error, setError] = useState("");
  const [guidanceError, setGuidanceError] = useState("");

  const pollCriticGuidance = useCallback(async (sessionId: string) => {
    setGuidanceLoading(true);
    setGuidanceError("");

    try {
      for (let attempt = 0; attempt < GUIDANCE_POLL_ATTEMPTS; attempt += 1) {
        const guidance = await fetchCriticGuidance(sessionId);
        setCriticGuidance(guidance);
        if (guidance.status === "ready" || guidance.status === "failed") {
          return;
        }
        await wait(GUIDANCE_POLL_INTERVAL_MS);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setGuidanceError(message);
    } finally {
      setGuidanceLoading(false);
    }
  }, []);

  const run = useCallback(async (request: ChatRequest) => {
    setLoading(true);
    setError("");
    setGuidanceError("");
    setCriticGuidance(null);

    try {
      const response = await fetchChat(request);
      setResult(response);
      void pollCriticGuidance(response.session_id);
      return response;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [pollCriticGuidance]);

  return {
    result,
    criticGuidance,
    loading,
    guidanceLoading,
    error,
    guidanceError,
    refreshGuidance: pollCriticGuidance,
    run,
  };
}
