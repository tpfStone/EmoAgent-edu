import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  CriticGuidanceStatusResponse,
  FullChatResponse,
} from "@emoedu/shared/console";
import { buildConsoleRunSessionId, SingleTurnTrace } from "./SingleTurnTrace";

const storedResponse: FullChatResponse = {
  session_id: "syn_0007-console-restored",
  anonymous_user_id: null,
  status: "answered",
  reply_text: "restored student-visible reply",
  risk_level: "green",
  scenario: "学业压力",
  support_mode: "balanced",
  emotion_intensity: "medium",
  help_seeking: true,
  selected_by: "fast_first_turn",
  activated_casel: ["自我管理引导"],
  best_candidate_id: "c2",
  candidates: [
    {
      candidate_id: "c2",
      orientation: "引导反思型",
      text: "restored candidate text",
    },
  ],
  scores: [],
  preference_pair: null,
  failed_module: null,
  failure_reason: "",
};

const storedGuidance: CriticGuidanceStatusResponse = {
  session_id: "syn_0007-console-restored",
  status: "ready",
  guidance: "Use concrete emotional acknowledgment.",
  scores: [
    {
      candidate_id: "c2",
      epitome: { ER: 1, IP: 1, EX: 1 },
      casel: { 自我管理引导: 1 },
      boundary_flag: false,
      boundary_reason: "",
      weighted_total: 3.5,
      rationale: "restored score",
    },
  ],
  error: "",
  updated_at: "2026-06-20T00:00:00Z",
};

describe("buildConsoleRunSessionId", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("keeps the sample prefix while creating a fresh id for each run", () => {
    vi.spyOn(Date, "now").mockReturnValueOnce(1710000000000).mockReturnValueOnce(1710000000001);
    vi.spyOn(Math, "random").mockReturnValueOnce(0.123456).mockReturnValueOnce(0.654321);

    const first = buildConsoleRunSessionId("syn_0007");
    const second = buildConsoleRunSessionId("syn_0007");

    expect(first).toMatch(/^syn_0007-console-/);
    expect(second).toMatch(/^syn_0007-console-/);
    expect(first).not.toBe(second);
  });

  it("restores the latest live run after a browser refresh", () => {
    localStorage.setItem(
      "emoagent.console.singleTurnTrace.v1",
      JSON.stringify({
        selectedId: "syn_0007",
        customInput: "我最近作业很多，有点烦，不知道怎么开始。",
        displayResult: storedResponse,
        criticGuidance: storedGuidance,
      }),
    );

    render(<SingleTurnTrace />);

    expect(
      screen.getByDisplayValue("我最近作业很多，有点烦，不知道怎么开始。"),
    ).toBeTruthy();
    expect(screen.getByText("syn_0007-console-restored")).toBeTruthy();
    expect(screen.getByText("restored student-visible reply")).toBeTruthy();
    expect(screen.getByText("F3 单候选")).toBeTruthy();
    expect(screen.queryByText("F3 双候选")).toBeNull();
    expect(screen.getByText("选中")).toBeTruthy();
  });
});
