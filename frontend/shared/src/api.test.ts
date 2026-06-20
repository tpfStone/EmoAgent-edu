import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchStudentChat } from "./api";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("fetchStudentChat", () => {
  it("projects the full chat response to the narrow student view", async () => {
    const view = await fetchStudentChat({
      session_id: "syn_0032",
      current_message: "最近和家里沟通很累，不知道怎么处理。",
    });

    expect(Object.keys(view)).toEqual([
      "session_id",
      "anonymous_user_id",
      "reply_text",
      "risk_level",
    ]);
    expect(view).toEqual({
      session_id: "syn_0032",
      anonymous_user_id: null,
      reply_text: expect.any(String),
      risk_level: expect.any(String),
    });
    expect(view).not.toHaveProperty("candidates");
    expect(view).not.toHaveProperty("scores");
    expect(view).not.toHaveProperty("preference_pair");
    expect(view).not.toHaveProperty("failure_reason");
  });

  it.each([
    "我最近真的不想活了。",
    "我不想存在了。",
    "我想直接消失。",
    "我想结束这一切。",
    "我觉得活着没意思。",
  ])("returns the red crisis sample for mock crisis wording: %s", async (message) => {
    const view = await fetchStudentChat({
      session_id: "student-session",
      current_message: message,
    });

    expect(view.risk_level).toBe("red");
  });
});

describe("fetchCriticGuidance", () => {
  it("fetches background F4 scores from the critic guidance endpoint in live mode", async () => {
    vi.stubEnv("VITE_API_MODE", "live");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        expect(url).toBe("/api/critic/guidance/session-1");
        return new Response(
          JSON.stringify({
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
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }),
    );

    const { fetchCriticGuidance } = await import("./api");
    const guidance = await fetchCriticGuidance("session-1");

    expect(guidance.status).toBe("ready");
    expect(guidance.scores).toHaveLength(1);
    expect(guidance.scores[0].weighted_total).toBe(5);
  });
});
