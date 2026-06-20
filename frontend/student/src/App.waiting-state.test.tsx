import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchStudentChatStream } from "@emoedu/shared";
import App from "./App";

vi.mock("@emoedu/shared", () => ({
  clearAnonymousMemory: vi.fn().mockResolvedValue(undefined),
  fetchStudentChatStream: vi.fn(),
}));

const fetchStudentChatStreamMock = vi.mocked(fetchStudentChatStream);

describe("student chat waiting state", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows a pending EmoAgent indicator until streamed text arrives", async () => {
    let onDelta: ((text: string) => void) | undefined;
    let resolveChat:
      | ((value: { session_id: string; reply_text: string; risk_level: "green" }) => void)
      | undefined;

    fetchStudentChatStreamMock.mockImplementation(async (_request, options) => {
      onDelta = options?.onDelta;
      return new Promise((resolve) => {
        resolveChat = resolve;
      });
    });

    render(<App />);

    const input = screen.getByRole("textbox", { name: "输入消息" });
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByLabelText("EmoAgent 正在回应")).toBeTruthy();

    onDelta?.("streamed reply");
    resolveChat?.({
      session_id: "student-session",
      reply_text: "streamed reply",
      risk_level: "green",
    });

    await waitFor(() => {
      expect(screen.queryByLabelText("EmoAgent 正在回应")).toBeNull();
    });
    expect(screen.getByText("streamed reply")).toBeTruthy();
  });
});
