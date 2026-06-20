import { useEffect } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchChat,
  fetchCriticGuidance,
  type CriticGuidanceStatusResponse,
  type FullChatResponse,
} from "@emoedu/shared/console";
import { useConsoleRun } from "./useConsoleRun";

vi.mock("@emoedu/shared/console", () => ({
  fetchChat: vi.fn(),
  fetchCriticGuidance: vi.fn(),
}));

const chatResponse: FullChatResponse = {
  session_id: "session-1",
  anonymous_user_id: null,
  status: "answered",
  reply_text: "student reply",
  risk_level: "green",
  scenario: null,
  support_mode: null,
  emotion_intensity: null,
  help_seeking: null,
  selected_by: "fast_first_turn",
  activated_casel: [],
  best_candidate_id: "c1",
  candidates: [],
  scores: [],
  preference_pair: null,
  failed_module: null,
  failure_reason: "",
};

const guidanceResponse: CriticGuidanceStatusResponse = {
  session_id: "session-1",
  status: "ready",
  guidance: "Use concrete emotional acknowledgment.",
  scores: [
    {
      candidate_id: "c1",
      epitome: { ER: 2, IP: 2, EX: 1 },
      casel: {},
      boundary_flag: false,
      boundary_reason: "",
      weighted_total: 5,
      rationale: "background label",
    },
  ],
  error: "",
  updated_at: "2026-06-16T00:00:00Z",
};

function Harness() {
  const { criticGuidance, result, run } = useConsoleRun();

  useEffect(() => {
    void run({ session_id: "session-1", current_message: "hello" });
  }, [run]);

  return (
    <div>
      <span data-testid="chat-scores">{result?.scores.length ?? -1}</span>
      <span data-testid="guidance-scores">
        {criticGuidance?.scores.length ?? -1}
      </span>
    </div>
  );
}

describe("useConsoleRun", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("loads background F4 scores after the fast chat response", async () => {
    vi.mocked(fetchChat).mockResolvedValue(chatResponse);
    vi.mocked(fetchCriticGuidance).mockResolvedValue(guidanceResponse);

    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByTestId("chat-scores").textContent).toBe("0");
      expect(screen.getByTestId("guidance-scores").textContent).toBe("1");
    });
    expect(fetchCriticGuidance).toHaveBeenCalledWith("session-1");
  });
});
