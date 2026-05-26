import { describe, expect, it } from "vitest";

import { fetchStudentChat } from "./api";

describe("fetchStudentChat", () => {
  it("projects the full chat response to the narrow student view", async () => {
    const view = await fetchStudentChat({
      session_id: "syn_0032",
      current_message: "最近和家里沟通很累，不知道怎么处理。",
    });

    expect(Object.keys(view)).toEqual(["session_id", "reply_text", "risk_level"]);
    expect(view).toEqual({
      session_id: "syn_0032",
      reply_text: expect.any(String),
      risk_level: expect.any(String),
    });
    expect(view).not.toHaveProperty("candidates");
    expect(view).not.toHaveProperty("scores");
    expect(view).not.toHaveProperty("preference_pair");
    expect(view).not.toHaveProperty("failure_reason");
  });

  it("returns the red crisis sample for crisis keywords in mock mode", async () => {
    const view = await fetchStudentChat({
      session_id: "student-session",
      current_message: "我最近真的不想活了。",
    });

    expect(view.risk_level).toBe("red");
  });
});
