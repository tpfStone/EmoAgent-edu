import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchStudentChatStream } from "@emoedu/shared";
import App from "./App";

vi.mock("@emoedu/shared", () => ({
  clearAnonymousMemory: vi.fn().mockResolvedValue(undefined),
  fetchStudentChatStream: vi.fn(),
}));

const fetchStudentChatStreamMock = vi.mocked(fetchStudentChatStream);

describe("student referral layout", () => {
  beforeEach(() => {
    localStorage.clear();
    fetchStudentChatStreamMock.mockResolvedValue({
      session_id: "session-a",
      anonymous_user_id: "anon-a",
      reply_text: "referral",
      risk_level: "red",
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("marks the chat scroll area when referral resources replace the composer", async () => {
    render(<App />);

    const input = screen.getByRole("textbox", { name: "输入消息" });
    fireEvent.change(input, { target: { value: "crisis" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("student-chat-scroll").dataset.referralLocked).toBe(
        "true",
      );
    });
    expect(screen.getByText("12356")).toBeTruthy();
    expect(screen.getByText("120")).toBeTruthy();
  });
});
