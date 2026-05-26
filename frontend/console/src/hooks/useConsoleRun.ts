import { useCallback, useState } from "react";
import { fetchChat, type ChatRequest, type FullChatResponse } from "@emoedu/shared/console";

export function useConsoleRun() {
  const [result, setResult] = useState<FullChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = useCallback(async (request: ChatRequest) => {
    setLoading(true);
    setError("");

    try {
      const response = await fetchChat(request);
      setResult(response);
      return response;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { result, loading, error, run };
}
